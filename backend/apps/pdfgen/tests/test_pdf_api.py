"""Build trigger, states, storage, download and permissions — the Celery task and
the API around it, with the task run eagerly."""
import shutil
import tempfile
import threading
from datetime import timedelta
from unittest import mock

from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import ROLL_CAPABILITIES, AccessRoll
from apps.core.constants import DocumentStatus
from apps.core.exceptions import ConflictError
from apps.documents.models import Document
from apps.pdfgen import adapter, services, storage, tasks
from apps.pdfgen.models import BUILD_STALE_AFTER, PdfBuild, PdfKind, PdfStatus

from . import cases as C
from .helpers import LOCMEM_CACHE, create_case, make_author

MEDIA = tempfile.mkdtemp(prefix="veye-pdfapi-media-")


def tearDownModule():
    shutil.rmtree(MEDIA, ignore_errors=True)


def eager():
    """Run the queued task inline instead of sending it to a broker."""
    return mock.patch.object(
        services.build_pdf, "delay", side_effect=lambda *args: services.build_pdf.apply(args=args)
    )


def url(name, document, kind):
    return reverse(name, kwargs={"document_id": document.pk, "kind": kind})


@override_settings(MEDIA_ROOT=MEDIA, FRONTEND_BASE_URL=C.FRONTEND, CACHES=LOCMEM_CACHE)
class PdfApiTests(TestCase):
    def setUp(self):
        self.user = make_author()
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.final = create_case("sample", {}, self.user)  # UNDER_CONTROL
        self.draft = create_case("draft_preview", {}, self.user)  # DRAFT

    def build(self, document, kind):
        with eager(), self.captureOnCommitCallbacks(execute=True):
            return self.client.post(url("pdf-build", document, kind))

    # -- the official PDF -------------------------------------------------

    def test_official_build_is_accepted_then_ready_and_downloadable(self):
        response = self.build(self.final, PdfKind.OFFICIAL)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data["status"], PdfStatus.BUILDING)  # what the POST saw

        status = self.client.get(url("pdf-build", self.final, PdfKind.OFFICIAL)).data
        self.assertEqual(status["status"], PdfStatus.READY)
        self.assertEqual(status["error"], "")
        self.assertGreater(status["size"], 10_000)
        self.assertTrue(status["download_url"].endswith(f"/documents/{self.final.pk}/pdf/official/download/"))

        build = PdfBuild.objects.get(document=self.final, kind=PdfKind.OFFICIAL)
        self.assertEqual(build.path, f"pdfs/{self.final.pk}/PR-01-01.pdf")
        pdf = storage.absolute_path(build.path).read_bytes()
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertEqual(len(pdf), build.size)
        import hashlib

        self.assertEqual(hashlib.sha256(pdf).hexdigest(), build.sha256)

        download = self.client.get(url("pdf-download", self.final, PdfKind.OFFICIAL))
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download["Content-Type"], "application/pdf")
        self.assertTrue(download["Content-Disposition"].startswith("inline"))
        self.assertIn("filename*=utf-8''", download["Content-Disposition"])
        self.assertEqual(b"".join(download.streaming_content), pdf)

        forced = self.client.get(url("pdf-download", self.final, PdfKind.OFFICIAL) + "?download=1")
        self.assertTrue(forced["Content-Disposition"].startswith("attachment"))

    def test_official_pdf_is_refused_for_an_unfinalized_document(self):
        response = self.build(self.draft, PdfKind.OFFICIAL)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "not_finalized")
        self.assertIn("نهایی", response.data["detail"])
        self.assertFalse(PdfBuild.objects.filter(document=self.draft).exists())

    def test_rebuild_replaces_the_file_in_place(self):
        self.build(self.final, PdfKind.OFFICIAL)
        build = PdfBuild.objects.get(document=self.final, kind=PdfKind.OFFICIAL)
        first_path, first_built = build.path, build.built_at

        Document.objects.filter(pk=self.final.pk).update(footnote1="پاورقی تازه")
        self.build(self.final, PdfKind.OFFICIAL)
        build.refresh_from_db()

        self.assertEqual(build.path, first_path)
        self.assertGreater(build.built_at, first_built)
        self.assertEqual(PdfBuild.objects.filter(document=self.final).count(), 1)
        self.assertEqual([p.name for p in storage.absolute_path(first_path).parent.iterdir()], ["PR-01-01.pdf"])

    def test_pdf_reflects_a_status_change_on_rebuild(self):
        # A document superseded by a newer revision must print «منسوخ» when rebuilt.
        self.build(self.final, PdfKind.OFFICIAL)
        before = storage.absolute_path(PdfBuild.objects.get(document=self.final).path).read_bytes()
        Document.objects.filter(pk=self.final.pk).update(status=DocumentStatus.OBSOLETE)
        self.build(self.final, PdfKind.OFFICIAL)
        after = storage.absolute_path(PdfBuild.objects.get(document=self.final).path).read_bytes()
        self.assertNotEqual(before, after)

    # -- the preview ------------------------------------------------------

    def test_preview_works_for_a_draft_and_is_kept_apart_from_the_official_pdf(self):
        self.assertEqual(self.build(self.draft, PdfKind.PREVIEW).status_code, 202)
        build = PdfBuild.objects.get(document=self.draft, kind=PdfKind.PREVIEW)
        self.assertEqual(build.status, PdfStatus.READY)
        self.assertEqual(build.path, f"pdf_previews/{self.draft.pk}.pdf")
        download = self.client.get(url("pdf-download", self.draft, PdfKind.PREVIEW))
        self.assertEqual(download.status_code, 200)
        # …and there is no official PDF to download for it.
        self.assertEqual(self.client.get(url("pdf-download", self.draft, PdfKind.OFFICIAL)).status_code, 404)

    def test_preview_is_watermarked_and_official_is_not(self):
        self.build(self.final, PdfKind.PREVIEW)
        self.build(self.final, PdfKind.OFFICIAL)
        preview = storage.absolute_path(f"pdf_previews/{self.final.pk}.pdf").read_bytes()
        official = storage.absolute_path(f"pdfs/{self.final.pk}/PR-01-01.pdf").read_bytes()
        self.assertNotEqual(preview, official)
        # The watermark is extra page content, so the preview is larger.
        self.assertGreater(len(preview), len(official) - 1)

    # -- states -----------------------------------------------------------

    def test_status_before_any_build_is_none(self):
        status = self.client.get(url("pdf-build", self.final, PdfKind.OFFICIAL)).data
        self.assertEqual(status["status"], "none")
        self.assertIsNone(status["download_url"])
        self.assertEqual(self.client.get(url("pdf-download", self.final, PdfKind.OFFICIAL)).status_code, 404)

    def test_a_second_request_while_building_is_a_typed_409(self):
        with mock.patch.object(services.build_pdf, "delay"), self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.post(url("pdf-build", self.final, PdfKind.OFFICIAL)).status_code, 202)
            response = self.client.post(url("pdf-build", self.final, PdfKind.OFFICIAL))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "build_in_progress")
        self.assertIsInstance(response.data["build_id"], int)

    def test_an_abandoned_build_can_be_restarted(self):
        with mock.patch.object(services.build_pdf, "delay"), self.captureOnCommitCallbacks(execute=True):
            self.client.post(url("pdf-build", self.final, PdfKind.OFFICIAL))
        PdfBuild.objects.update(requested_at=timezone.now() - BUILD_STALE_AFTER - timedelta(seconds=1))
        self.assertTrue(self.client.get(url("pdf-build", self.final, PdfKind.OFFICIAL)).data["stale"])
        self.assertEqual(self.build(self.final, PdfKind.OFFICIAL).status_code, 202)
        self.assertEqual(PdfBuild.objects.get().status, PdfStatus.READY)

    def test_a_failed_build_reports_a_persian_error_and_can_be_retried(self):
        with eager(), mock.patch.object(adapter, "load", side_effect=RuntimeError("boom")), \
                self.captureOnCommitCallbacks(execute=True):
            self.client.post(url("pdf-build", self.final, PdfKind.OFFICIAL))
        status = self.client.get(url("pdf-build", self.final, PdfKind.OFFICIAL)).data
        self.assertEqual(status["status"], PdfStatus.FAILED)
        self.assertEqual(status["error"], tasks.FAILED_GENERIC)
        self.assertNotIn("boom", status["error"])  # the cause is logged, not shown
        self.assertIsNone(status["download_url"])
        self.assertEqual(self.build(self.final, PdfKind.OFFICIAL).status_code, 202)
        self.assertEqual(PdfBuild.objects.get().status, PdfStatus.READY)

    def test_a_failed_rebuild_keeps_the_previous_file_downloadable(self):
        self.build(self.final, PdfKind.OFFICIAL)
        with eager(), mock.patch.object(adapter, "load", side_effect=RuntimeError), \
                self.captureOnCommitCallbacks(execute=True):
            self.client.post(url("pdf-build", self.final, PdfKind.OFFICIAL))
        status = self.client.get(url("pdf-build", self.final, PdfKind.OFFICIAL)).data
        self.assertEqual(status["status"], PdfStatus.FAILED)
        self.assertIsNotNone(status["download_url"])
        self.assertEqual(self.client.get(url("pdf-download", self.final, PdfKind.OFFICIAL)).status_code, 200)

    def test_an_unreachable_broker_fails_the_build_immediately(self):
        with mock.patch.object(services.build_pdf, "delay", side_effect=ConnectionError), \
                self.captureOnCommitCallbacks(execute=True):
            self.client.post(url("pdf-build", self.final, PdfKind.OFFICIAL))
        build = PdfBuild.objects.get()
        self.assertEqual(build.status, PdfStatus.FAILED)
        self.assertIn("در دسترس نیست", build.error)

    # -- the task itself --------------------------------------------------

    def test_task_ignores_a_superseded_or_repeated_delivery(self):
        with mock.patch.object(services.build_pdf, "delay"), self.captureOnCommitCallbacks(execute=True):
            self.client.post(url("pdf-build", self.final, PdfKind.OFFICIAL))
        build = PdfBuild.objects.get()
        self.assertEqual(tasks.build_pdf.apply(args=(build.pk, "stale-token")).get(), "skipped")
        build.refresh_from_db()
        self.assertEqual(build.status, PdfStatus.BUILDING)

        self.assertEqual(tasks.build_pdf.apply(args=(build.pk, build.token)).get(), "ready")
        self.assertEqual(tasks.build_pdf.apply(args=(build.pk, build.token)).get(), "skipped")  # redelivery

    def test_a_disk_error_is_retried_then_reported(self):
        with eager(), mock.patch.object(storage, "write_atomic", side_effect=OSError("disk full")) as write, \
                self.captureOnCommitCallbacks(execute=True):
            self.client.post(url("pdf-build", self.final, PdfKind.OFFICIAL))
        self.assertEqual(write.call_count, tasks.build_pdf.max_retries + 1)
        self.assertEqual(PdfBuild.objects.get().status, PdfStatus.FAILED)

    def test_write_atomic_never_leaves_a_torn_or_temporary_file(self):
        storage.write_atomic("pdfs/x/a.pdf", b"old")
        target = storage.absolute_path("pdfs/x/a.pdf")
        with mock.patch("apps.pdfgen.storage.os.replace", side_effect=OSError):
            with self.assertRaises(OSError):
                storage.write_atomic("pdfs/x/a.pdf", b"new")
        self.assertEqual(target.read_bytes(), b"old")
        self.assertEqual([p.name for p in target.parent.iterdir()], ["a.pdf"])

    def test_paths_cannot_escape_the_media_root(self):
        with self.assertRaises(ValueError):
            storage.absolute_path("../outside.pdf")

    def test_fresh_empty_media_root_is_created_on_demand(self):
        with tempfile.TemporaryDirectory() as empty, override_settings(MEDIA_ROOT=empty):
            self.build(self.final, PdfKind.OFFICIAL)
            self.assertEqual(PdfBuild.objects.get().status, PdfStatus.READY)
            self.assertTrue((storage.absolute_path(f"pdfs/{self.final.pk}") / "PR-01-01.pdf").is_file())

    # -- access -----------------------------------------------------------

    def test_requires_authentication(self):
        anonymous = APIClient()
        for method, name in (("get", "pdf-build"), ("post", "pdf-build"), ("get", "pdf-download")):
            response = getattr(anonymous, method)(url(name, self.final, PdfKind.OFFICIAL))
            self.assertEqual(response.status_code, 401, (method, name))

    def test_building_needs_the_print_capability_but_reading_does_not(self):
        limited = {roll: caps - {"print_document"} for roll, caps in ROLL_CAPABILITIES.items()}
        with mock.patch.dict(ROLL_CAPABILITIES, limited):
            self.assertEqual(self.client.post(url("pdf-build", self.final, PdfKind.OFFICIAL)).status_code, 403)
            self.assertEqual(self.client.get(url("pdf-build", self.final, PdfKind.OFFICIAL)).status_code, 200)

    def test_every_roll_may_build_by_default(self):
        for roll in AccessRoll.values:
            self.assertIn("print_document", ROLL_CAPABILITIES[roll], roll)

    def test_unknown_kind_and_unknown_document_are_404(self):
        self.assertEqual(self.client.get(f"/api/v1/documents/{self.final.pk}/pdf/nope/").status_code, 404)
        self.assertEqual(self.client.post(f"/api/v1/documents/{self.final.pk}/pdf/nope/").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/documents/999999/pdf/official/").status_code, 404)
        self.assertEqual(self.client.post("/api/v1/documents/999999/pdf/official/").status_code, 404)

    # -- the register never renders ---------------------------------------

    def test_register_list_reports_pdf_state_without_touching_the_renderer(self):
        self.build(self.final, PdfKind.OFFICIAL)
        with mock.patch("apps.pdfgen.renderer.PDFMaker.__init__", side_effect=AssertionError("rendered")), \
                mock.patch.object(adapter, "load", side_effect=AssertionError("loaded")), \
                mock.patch.object(services, "request_build", side_effect=AssertionError("built")):
            response = self.client.get(reverse("document-list"))
        self.assertEqual(response.status_code, 200)
        rows = {row["id"]: row for row in response.data["results"]}
        self.assertEqual(rows[self.final.pk]["pdf_status"], PdfStatus.READY)
        self.assertIsNotNone(rows[self.final.pk]["pdf_built_at"])
        self.assertEqual(rows[self.draft.pk]["pdf_status"], "none")
        self.assertIsNone(rows[self.draft.pk]["pdf_built_at"])

    def test_register_list_costs_the_same_number_of_queries_with_pdf_state(self):
        # count + page + sign-offs + responsibility sections (unchanged by Phase 4).
        with self.assertNumQueries(4):
            self.client.get(reverse("document-list"))

    def test_single_document_responses_carry_the_official_state_too(self):
        self.build(self.final, PdfKind.OFFICIAL)
        data = self.client.get(reverse("document-detail", args=[self.final.pk])).data
        self.assertEqual(data["pdf_status"], PdfStatus.READY)


@override_settings(MEDIA_ROOT=MEDIA, FRONTEND_BASE_URL=C.FRONTEND, CACHES=LOCMEM_CACHE)
class ConcurrentRequestTests(TransactionTestCase):
    """Two people clicking «ساخت PDF» at the same moment: exactly one build starts."""

    @skipUnlessDBFeature("has_select_for_update")
    def test_simultaneous_first_requests_start_exactly_one_build(self):
        self.race(existing=False)

    @skipUnlessDBFeature("has_select_for_update")
    def test_simultaneous_rebuilds_start_exactly_one_build(self):
        # The row already exists (READY), so it is the row lock — not the unique
        # constraint — that stops both requests from passing the "not building" check.
        self.race(existing=True)

    def race(self, existing):
        user = make_author()
        document = create_case("sample", {}, user)
        if existing:
            PdfBuild.objects.create(
                document=document, kind=PdfKind.OFFICIAL, status=PdfStatus.READY, token="old",
                path="pdfs/x.pdf", built_at=timezone.now(),
            )
        barrier = threading.Barrier(2)
        outcomes = []

        def request():
            try:
                barrier.wait()
                services.request_build(user=user, document_id=document.pk, kind=PdfKind.OFFICIAL)
                outcomes.append("started")
            except ConflictError as error:
                outcomes.append(error.payload["code"])
            finally:
                connection.close()

        with mock.patch.object(services.build_pdf, "delay") as delay:
            threads = [threading.Thread(target=request) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        self.assertEqual(sorted(outcomes), ["build_in_progress", "started"])
        self.assertEqual(delay.call_count, 1)
        self.assertEqual(PdfBuild.objects.filter(document=document).count(), 1)
