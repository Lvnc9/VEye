"""چاپ لیست: the ZIP of already-built PDFs (Phase 6)."""
import io
import shutil
import tempfile
import zipfile
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.core.constants import DocumentStatus
from apps.core.exceptions import ConflictError
from apps.pdfgen import adapter, bulk, services, storage
from apps.pdfgen.models import PdfBuild, PdfKind, PdfStatus

from . import cases as C
from .helpers import LOCMEM_CACHE, create_case, make_author

MEDIA = tempfile.mkdtemp(prefix="veye-bulk-media-")


def tearDownModule():
    shutil.rmtree(MEDIA, ignore_errors=True)


def eager():
    return mock.patch.object(
        services.build_pdf, "delay", side_effect=lambda *args: services.build_pdf.apply(args=args)
    )


@override_settings(MEDIA_ROOT=MEDIA, FRONTEND_BASE_URL=C.FRONTEND, CACHES=LOCMEM_CACHE)
class BulkPrintTests(TestCase):
    def setUp(self):
        self.user = make_author()
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        created = {}
        self.sample = create_case("sample", created, self.user)   # PR-01-01 under control
        self.bare = create_case("bare", created, self.user)       # PO-02-01 under control
        self.full = create_case("full", created, self.user)       # WI-03-02 obsolete (rev 2)
        self.draft = create_case("draft_preview", created, self.user)  # FR-04-01 draft
        # Earlier revision WI-03-01 (under control, never built) was made for `full`.
        self.previous = self.full.previous_revision

    def build(self, *documents):
        for document in documents:
            with eager(), self.captureOnCommitCallbacks(execute=True):
                services.request_build(user=self.user, document_id=document.pk, kind=PdfKind.OFFICIAL)

    def ids(self, *documents):
        return {"ids": ",".join(str(d.pk) for d in documents)}

    def preflight(self, **params):
        return self.client.get(reverse("bulk-print-preflight"), params)

    def download(self, **params):
        return self.client.get(reverse("bulk-print"), params)

    def names(self, response):
        with zipfile.ZipFile(io.BytesIO(b"".join(response.streaming_content))) as archive:
            self.assertIsNone(archive.testzip())
            return archive.namelist()

    # -- the preflight ------------------------------------------------------

    def test_preflight_separates_ready_documents_from_missing_ones_with_reasons(self):
        self.build(self.sample, self.bare)
        data = self.preflight(**self.ids(self.sample, self.bare, self.full, self.draft, self.previous)).data
        self.assertEqual((data["total"], data["ready"], data["truncated"]), (5, 2, False))
        reasons = {m["full_code"]: m["reason"] for m in data["missing"]}
        self.assertEqual(reasons, {"WI-03-02": "not_built", "FR-04-01": "not_finalized", "WI-03-01": "not_built"})
        labels = {m["reason"]: m["reason_label"] for m in data["missing"]}
        self.assertEqual(labels["not_finalized"], "هنوز نهایی نشده است")
        self.assertEqual(labels["not_built"], "PDF ساخته نشده است")

    def test_a_document_whose_file_vanished_is_reported_not_zipped(self):
        self.build(self.sample)
        storage.absolute_path(PdfBuild.objects.get(document=self.sample).path).unlink()
        data = self.preflight(**self.ids(self.sample)).data
        self.assertEqual((data["ready"], data["missing"][0]["reason"]), (0, "file_missing"))

    def test_building_and_failed_builds_without_a_file_are_reported(self):
        PdfBuild.objects.create(document=self.sample, kind=PdfKind.OFFICIAL, status=PdfStatus.BUILDING)
        PdfBuild.objects.create(document=self.bare, kind=PdfKind.OFFICIAL, status=PdfStatus.FAILED, error="x")
        reasons = {m["full_code"]: m["reason"] for m in self.preflight(**self.ids(self.sample, self.bare)).data["missing"]}
        self.assertEqual(reasons, {"PR-01-01": "building", "PO-02-01": "failed"})

    def test_a_rebuild_in_progress_still_offers_the_previous_file(self):
        self.build(self.sample)
        PdfBuild.objects.filter(document=self.sample).update(status=PdfStatus.BUILDING)
        self.assertEqual(self.preflight(**self.ids(self.sample)).data["ready"], 1)

    def test_a_preview_is_never_a_bulk_print_candidate(self):
        with eager(), self.captureOnCommitCallbacks(execute=True):
            services.request_build(user=self.user, document_id=self.sample.pk, kind=PdfKind.PREVIEW)
        self.assertEqual(self.preflight(**self.ids(self.sample)).data["ready"], 0)

    # -- the ZIP ------------------------------------------------------------

    def test_zip_holds_exactly_the_ready_pdfs_named_title_code_and_byte_identical(self):
        self.build(self.sample, self.bare)
        response = self.download(**self.ids(self.sample, self.bare, self.draft))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")
        self.assertTrue(response["Content-Disposition"].startswith("attachment"))
        self.assertEqual((response["X-Bulk-Print-Count"], response["X-Bulk-Print-Missing"]), ("2", "1"))
        self.assertEqual(response["Cache-Control"], "private, no-store")
        payload = b"".join(response.streaming_content)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            self.assertEqual(sorted(archive.namelist()), sorted([
                f"{self.sample.title}-PR-01-01.pdf", f"{self.bare.title}-PO-02-01.pdf"]))
            for document in (self.sample, self.bare):
                expected = storage.absolute_path(PdfBuild.objects.get(document=document).path).read_bytes()
                self.assertEqual(archive.read(f"{document.title}-{document.full_code}.pdf"), expected)

    def test_entries_follow_the_printed_code_order(self):
        self.build(self.sample, self.bare)
        self.assertEqual(self.names(self.download(**self.ids(self.sample, self.bare))),
                         [f"{self.bare.title}-PO-02-01.pdf", f"{self.sample.title}-PR-01-01.pdf"])  # PO before PR

    def test_nothing_ready_is_a_typed_409_with_a_persian_message(self):
        response = self.download(**self.ids(self.draft, self.full))
        self.assertEqual((response.status_code, response.data["code"]), (409, "nothing_to_print"))
        self.assertEqual(response.data["missing"], 2)
        self.assertIn("PDF", response.data["detail"])

    # -- the selection ------------------------------------------------------

    def test_without_ids_it_follows_the_registers_filters(self):
        self.build(self.sample, self.bare)
        self.assertEqual(self.preflight(group="PROCEDURE").data["total"], 1)   # sample
        self.assertEqual(self.preflight(group="INSTRUCTION").data["total"], 2)  # WI-03 rev 1 and 2
        data = self.preflight(status="UNDER_CONTROL").data
        self.assertEqual((data["total"], data["ready"]), (3, 2))               # sample, bare, previous revision
        self.assertEqual(self.names(self.download(group="POSTER")), [f"{self.bare.title}-PO-02-01.pdf"])
        self.assertEqual(self.preflight(search="PR-01-01").data["total"], 1)   # the register's search box

    def test_an_unknown_filter_value_selects_nothing_rather_than_everything(self):
        self.build(self.sample)
        data = self.preflight(status="NOPE").data
        self.assertEqual((data["total"], data["ready"]), (0, 0))
        self.assertEqual(self.download(status="NOPE").status_code, 409)

    def test_no_filters_at_all_means_every_document(self):
        self.assertEqual(self.preflight().data["total"], 5)

    def test_bad_ids_are_a_400(self):
        for raw in ("abc", "1,x", "1;2"):
            self.assertEqual(self.preflight(ids=raw).status_code, 400, raw)
        self.assertEqual(self.preflight(ids=",".join(["1"] * 1001)).status_code, 400)

    def test_duplicate_ids_are_collapsed(self):
        self.build(self.sample)
        self.assertEqual(self.preflight(ids=f"{self.sample.pk},{self.sample.pk}").data["total"], 1)

    def test_an_unknown_id_is_simply_not_selected(self):
        self.assertEqual(self.preflight(ids="999999").data["total"], 0)

    # -- the cap ------------------------------------------------------------

    def test_the_cap_trims_the_zip_and_says_so(self):
        self.build(self.sample, self.bare)
        with override_settings(BULK_PRINT_MAX_FILES=1):
            data = self.preflight(status="UNDER_CONTROL").data
            self.assertEqual((data["total"], data["cap"], data["truncated"]), (3, 1, True))
            self.assertEqual(data["ready"] + len(data["missing"]), 1)
            # The first by printed code: PO-02-01.
            self.assertEqual(self.names(self.download(status="UNDER_CONTROL")), [f"{self.bare.title}-PO-02-01.pdf"])

    # -- it never renders ---------------------------------------------------

    def test_bulk_print_never_renders_or_builds_anything(self):
        self.build(self.sample)
        with mock.patch("apps.pdfgen.renderer.PDFMaker.__init__", side_effect=AssertionError("rendered")), \
                mock.patch.object(adapter, "load", side_effect=AssertionError("loaded")), \
                mock.patch.object(services, "request_build", side_effect=AssertionError("built")):
            self.assertEqual(self.names(self.download(**self.ids(self.sample, self.draft))), [f"{self.sample.title}-PR-01-01.pdf"])
            self.assertEqual(self.preflight(**self.ids(self.sample, self.draft)).status_code, 200)
        self.assertEqual(PdfBuild.objects.count(), 1)

    # -- access & cost ------------------------------------------------------

    def test_requires_authentication(self):
        for name in ("bulk-print-preflight", "bulk-print"):
            self.assertEqual(APIClient().get(reverse(name)).status_code, 401, name)

    def test_the_route_is_not_swallowed_by_the_documents_detail_route(self):
        self.assertEqual(reverse("bulk-print"), "/api/v1/documents/bulk-print/")
        self.assertEqual(self.preflight(**self.ids(self.sample)).status_code, 200)

    def test_preflight_costs_three_queries_however_many_documents(self):
        self.build(self.sample, self.bare)
        with self.assertNumQueries(3):  # count + documents + build rows
            self.preflight()


class ArchiveNameTests(TestCase):
    def doc(self, title, code="PR-01-01"):
        return SimpleNamespace(title=title, full_code=code)

    def test_unsafe_characters_cannot_escape_the_archive_or_break_the_name(self):
        name = bulk.archive_name(self.doc("../../etc/passwd: a*b?c\"d<e>f|g"), set())
        self.assertNotIn("/", name)
        self.assertNotIn("\\", name)
        self.assertTrue(name.endswith("-PR-01-01.pdf"))
        self.assertFalse(name.startswith("."))

    def test_persian_titles_are_kept_and_empty_ones_get_a_fallback(self):
        self.assertEqual(bulk.archive_name(self.doc("روش اجرایی کنترل"), set()), "روش اجرایی کنترل-PR-01-01.pdf")
        self.assertEqual(bulk.archive_name(self.doc("  .. "), set()), "document-PR-01-01.pdf")

    def test_colliding_names_are_numbered(self):
        taken = set()
        first = bulk.archive_name(self.doc("عنوان"), taken)
        second = bulk.archive_name(self.doc("عنوان"), taken)
        self.assertEqual((first, second), ("عنوان-PR-01-01.pdf", "عنوان-PR-01-01 (2).pdf"))
