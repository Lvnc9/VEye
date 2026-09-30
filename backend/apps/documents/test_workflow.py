"""The sign-off workflow (Phase 5) and the public verify endpoint."""
import shutil
import tempfile
import threading
from datetime import date, timedelta
from io import BytesIO
from unittest import mock

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone
from PIL import Image, ImageDraw
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from apps.accounts.models import AccessLevel, AccessRoll, User
from apps.accounts.models import Capability
from apps.core.constants import (
    DocumentCategory,
    DocumentEventKind,
    DocumentGroup,
    DocumentStatus,
    SignOffRole,
)
from apps.core.exceptions import ConflictError
from apps.dashboard.views import METRICS_CACHE_KEY
from apps.pdfgen.models import PdfBuild, PdfKind, PdfStatus

from . import services, test_support, workflow
from .models import Document, DocumentEvent, SignOff

MEDIA = tempfile.mkdtemp(prefix="veye-workflow-media-")
LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "veye-workflow-tests"}}


def tearDownModule():
    shutil.rmtree(MEDIA, ignore_errors=True)


def signature_bytes(color=(10, 10, 120), size=(200, 90), fmt="PNG", alpha=False) -> bytes:
    mode = "RGBA" if alpha else "RGB"
    background = (0, 0, 0, 0) if alpha else (255, 255, 255)
    image = Image.new(mode, size, background)
    draw = ImageDraw.Draw(image)
    draw.line([(10, 60), (60, 20), (110, 70), (180, 30)], fill=color + ((255,) if alpha else ()), width=4)
    buffer = BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def upload(data=None, name="signature.png", content_type="image/png"):
    return {"signature": SimpleUploadedFile(name, data if data is not None else signature_bytes(), content_type)}


def make_user(code, roll, level=AccessLevel.LEVEL_2, **extra):
    return User.objects.create_user(
        national_code=code, password="pw-for-tests-123", full_name=f"کاربر {code}",
        access_roll=roll, access_level=level, **extra,
    )


def make_doc(author, title="سند گردش", group=DocumentGroup.PROCEDURE, saved=True, owner_node=None, **extra) -> Document:
    doc = services.create_document(
        user=author, category=DocumentCategory.INSIDE, title=title, group=group,
        owner_node=owner_node or test_support.ensure_org().rag,
    )
    if saved:
        Document.objects.filter(pk=doc.pk).update(content_saved_at=timezone.now())
        doc.refresh_from_db()
    for key, value in extra.items():
        Document.objects.filter(pk=doc.pk).update(**{key: value})
    doc.refresh_from_db()
    return doc


@override_settings(MEDIA_ROOT=MEDIA, CACHES=LOCMEM, RATELIMIT_ENABLE=False)
class WorkflowBase(TestCase):
    def setUp(self):
        cache.clear()
        # The chart decides (Phase 14): the document belongs to the بخش «RAG»; its مسئول writes it, the مسئول of
        # the واحد above (هوش مصنوعی) confirms it, the مدیر عامل approves.
        self.org = test_support.ensure_org()
        self.author = make_user("8000000001", AccessRoll.GUILD)
        test_support.lead_of(self.author, self.org.rag)
        self.confirmer = make_user("8000000002", AccessRoll.HEADQUARTERS)
        test_support.lead_of(self.confirmer, self.org.ai)
        self.confirmer2 = make_user("8000000003", AccessRoll.HEADQUARTERS, AccessLevel.LEVEL_1)
        test_support.lead_of(self.confirmer2, self.org.ai)
        self.approver = make_user("8000000004", AccessRoll.EMPLOYER, AccessLevel.LEVEL_1)  # the مدیر عامل
        self.doc = make_doc(self.author)

    def as_user(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def act(self, user, verb, doc=None, **payload):
        doc = doc or self.doc
        client = self.as_user(user)
        if verb == "return":
            return client.post(reverse("document-return-to-draft", args=[doc.pk]), payload, format="json")
        body = payload or upload()
        return client.post(reverse(f"document-{verb}", args=[doc.pk]), body, format="multipart")

    def run_chain(self, doc=None):
        for user, verb in ((self.author, "submit"), (self.confirmer, "confirm"), (self.approver, "approve")):
            with mock.patch("apps.pdfgen.services.build_pdf.delay"), self.captureOnCommitCallbacks(execute=True):
                response = self.act(user, verb, doc)
            self.assertEqual(response.status_code, 200, (verb, response.data))
        return Document.objects.get(pk=(doc or self.doc).pk)


class HappyPathTests(WorkflowBase):
    def test_submitting_locks_the_body(self):
        response = self.act(self.author, "submit")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], DocumentStatus.AWAITING_CONFIRMATION)
        self.assertFalse(Document.objects.get(pk=self.doc.pk).is_editable)

    def test_signers_are_the_signed_in_users_never_what_the_request_claims(self):
        client = self.as_user(self.author)
        body = {**upload(), "name": "شخص دیگر", "position": "مدیر عامل", "signed_by": "1"}
        response = client.post(reverse("document-submit", args=[self.doc.pk]), body, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        signoff = SignOff.objects.get(document=self.doc, role=SignOffRole.CREATER)
        self.assertEqual(signoff.name, self.author.full_name)
        self.assertEqual(signoff.position, self.author.title)
        self.assertEqual(signoff.signed_by_id, self.author.pk)
        self.assertEqual(signoff.signed_date, timezone.localdate())
        self.assertTrue(signoff.signature.name.startswith(f"signatures/{self.doc.pk}/"))
        self.assertTrue(signoff.signature.name.endswith(".png"))

    def test_three_signatures_end_under_control_with_an_audit_trail(self):
        doc = self.run_chain()
        self.assertEqual(doc.status, DocumentStatus.UNDER_CONTROL)
        roles = {s.role: s for s in doc.signoffs.all()}
        self.assertEqual(set(roles), {SignOffRole.CREATER, SignOffRole.CONFIRMER, SignOffRole.APPROVER})
        self.assertEqual(roles[SignOffRole.CONFIRMER].signed_by_id, self.confirmer.pk)
        self.assertEqual(roles[SignOffRole.APPROVER].position, self.approver.title)

        events = list(doc.events.all())
        self.assertEqual([e.kind for e in events], [
            DocumentEventKind.SUBMITTED, DocumentEventKind.CONFIRMED, DocumentEventKind.APPROVED])
        self.assertEqual([e.to_status for e in events], [
            DocumentStatus.AWAITING_CONFIRMATION, DocumentStatus.AWAITING_APPROVAL, DocumentStatus.UNDER_CONTROL])
        self.assertEqual(events[1].actor_name, self.confirmer.full_name)
        self.assertEqual(events[1].actor_title, self.confirmer.title)

    def test_the_register_shows_the_signers_once_signed(self):
        self.run_chain()
        row = self.as_user(self.author).get(reverse("document-detail", args=[self.doc.pk])).data
        self.assertEqual(row["signoffs"]["confirmer"]["name"], self.confirmer.full_name)
        self.assertEqual(row["action"], "print")

    def test_every_transition_invalidates_the_dashboard_cache(self):
        cache.set(METRICS_CACHE_KEY, {"stale": True})
        with mock.patch("apps.pdfgen.services.build_pdf.delay"):
            self.act(self.author, "submit")
        self.assertIsNone(cache.get(METRICS_CACHE_KEY))

    def test_approving_builds_the_official_pdf(self):
        with mock.patch("apps.pdfgen.services.build_pdf.delay") as delay:
            for user, verb in ((self.author, "submit"), (self.confirmer, "confirm"), (self.approver, "approve")):
                with self.captureOnCommitCallbacks(execute=True):
                    self.act(user, verb)
        build = PdfBuild.objects.get(document=self.doc, kind=PdfKind.OFFICIAL)
        self.assertEqual(build.status, PdfStatus.BUILDING)
        self.assertEqual(build.requested_by_id, self.approver.pk)
        self.assertEqual(delay.call_count, 1)


class GuardTests(WorkflowBase):
    def test_out_of_order_steps_are_typed_409s(self):
        for user, verb in ((self.confirmer, "confirm"), (self.approver, "approve")):
            response = self.act(user, verb)  # a DRAFT can be neither
            self.assertEqual(response.status_code, 409, verb)
            self.assertEqual(response.data["code"], "wrong_status")
            self.assertEqual(response.data["status"], DocumentStatus.DRAFT)
        with mock.patch("apps.pdfgen.services.build_pdf.delay"):
            self.act(self.author, "submit")
        again = self.act(self.author, "submit")
        self.assertEqual((again.status_code, again.data["code"]), (409, "wrong_status"))
        self.assertEqual(self.act(self.approver, "approve").data["code"], "wrong_status")  # not yet confirmed

    def test_submitting_needs_a_saved_body(self):
        empty = make_doc(self.author, title="خالی", saved=False)
        response = self.act(self.author, "submit", empty)
        self.assertEqual((response.status_code, response.data["code"]), (409, "content_missing"))
        self.assertEqual(Document.objects.get(pk=empty.pk).status, DocumentStatus.DRAFT)
        self.assertFalse(SignOff.objects.filter(document=empty).exists())

    def test_each_step_follows_the_chart(self):
        outsider = make_user("8000000020", AccessRoll.GUILD)  # placed nowhere
        elsewhere = make_user("8000000021", AccessRoll.GUILD)
        test_support.lead_of(elsewhere, self.org.llm)  # leads another بخش
        self.assertEqual(self.act(self.author, "submit").status_code, 200)  # the مسئول of RAG writes its document
        self.assertEqual(self.act(self.author, "confirm").status_code, 403)  # …but a بخش's lead never confirms
        self.assertEqual(self.act(self.confirmer, "approve").status_code, 403)  # the واحد's lead does not approve
        self.assertEqual(self.act(elsewhere, "confirm").status_code, 403)
        for user in (outsider, elsewhere):
            other = make_doc(self.author, title=f"دیگر {user.pk}")
            self.assertEqual(self.act(user, "submit", other).status_code, 403, user.national_code)

    def test_a_roll_no_longer_grants_a_step(self):
        # A ستادی who leads nothing, and a board member: neither writes nor confirms (only the chart decides).
        staff = make_user("8000000022", AccessRoll.HEADQUARTERS, AccessLevel.LEVEL_1)
        chair = make_user("8000000023", AccessRoll.EMPLOYER, AccessLevel.LEVEL_2)
        self.assertEqual(self.act(staff, "submit").status_code, 403)
        self.assertEqual(self.act(chair, "submit").status_code, 403)
        with mock.patch("apps.pdfgen.services.build_pdf.delay"):
            self.act(self.author, "submit")
        self.assertEqual(self.act(staff, "confirm").status_code, 403)
        self.assertEqual(self.act(chair, "confirm").status_code, 403)
        with mock.patch("apps.pdfgen.services.build_pdf.delay"):
            self.act(self.confirmer, "confirm")
        self.assertEqual(self.act(chair, "approve").status_code, 403, "the board does not approve: only the مدیر عامل")

    def test_anonymous_callers_are_refused(self):
        for verb in ("submit", "confirm", "approve", "return-to-draft", "history"):
            client = APIClient()
            method = client.get if verb == "history" else client.post
            self.assertEqual(method(reverse(f"document-{verb}", args=[self.doc.pk])).status_code, 401, verb)

    def test_the_same_person_may_write_and_confirm(self):
        """Owner's decision 2026-09-30: «one person per step» is retired — a مسئول who writes a document
        of their own واحد may also confirm it."""
        mine = make_doc(self.confirmer, title="سند واحد", owner_node=self.org.ai)
        with mock.patch("apps.pdfgen.services.build_pdf.delay"), self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.act(self.confirmer, "submit", mine).status_code, 200)
            self.assertEqual(self.act(self.confirmer, "confirm", mine).status_code, 200)
            self.assertEqual(self.act(self.approver, "approve", mine).status_code, 200)
        self.assertEqual(Document.objects.get(pk=mine.pk).status, DocumentStatus.UNDER_CONTROL)
        signers = set(SignOff.objects.filter(document=mine).values_list("signed_by_id", flat=True))
        self.assertEqual(signers, {self.confirmer.pk, self.approver.pk})

    def test_only_the_managing_director_approves(self):
        with mock.patch("apps.pdfgen.services.build_pdf.delay"):
            self.act(self.author, "submit")
            self.assertEqual(self.act(self.confirmer, "confirm").status_code, 200)
        self.assertEqual(self.act(self.confirmer, "approve").status_code, 403)
        self.assertEqual(self.act(self.confirmer2, "approve").status_code, 403)
        domain_lead = make_user("8000000024", AccessRoll.HEADQUARTERS)
        test_support.lead_of(domain_lead, self.org.it)
        self.assertEqual(self.act(domain_lead, "approve").status_code, 403)
        with mock.patch("apps.pdfgen.services.build_pdf.delay"):
            self.assertEqual(self.act(self.approver, "approve").status_code, 200)

    def test_a_failed_step_leaves_nothing_behind(self):
        self.assertEqual(self.act(self.author, "submit").status_code, 200)
        refused = self.as_user(self.confirmer).post(
            reverse("document-confirm", args=[self.doc.pk]), {"signature": SimpleUploadedFile("s.png", b"nope")}, format="multipart"
        )
        self.assertEqual(refused.status_code, 400)
        self.assertEqual(Document.objects.get(pk=self.doc.pk).status, DocumentStatus.AWAITING_CONFIRMATION)
        self.assertFalse(SignOff.objects.filter(document=self.doc, role=SignOffRole.CONFIRMER).exists())
        self.assertEqual(self.doc.events.count(), 1)


class SignatureTests(WorkflowBase):
    def submit(self, files):
        return self.as_user(self.author).post(reverse("document-submit", args=[self.doc.pk]), files, format="multipart")

    def test_missing_signature(self):
        response = self.as_user(self.author).post(reverse("document-submit", args=[self.doc.pk]), {}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("امضا", response.data["signature"][0])

    def test_not_an_image(self):
        response = self.submit(upload(b"definitely not a png"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.doc.signoffs.count(), 0)

    def test_a_blank_pad_is_not_a_signature(self):
        blank = BytesIO()
        Image.new("RGB", (200, 90), (255, 255, 255)).save(blank, format="PNG")
        response = self.submit(upload(blank.getvalue()))
        self.assertEqual(response.status_code, 400)
        self.assertIn("خالی", response.data["signature"][0])

    def test_oversized_upload_is_refused(self):
        with mock.patch("apps.documents.files.SIGNATURE_MAX_BYTES", 100):
            self.assertEqual(self.submit(upload()).status_code, 400)

    def test_a_transparent_pad_export_is_stored_opaque_white(self):
        # The renderer draws signatures unmasked: transparency would print black.
        self.assertEqual(self.submit(upload(signature_bytes(alpha=True))).status_code, 200)
        signoff = self.doc.signoffs.get()
        with signoff.signature.open("rb") as handle:
            image = Image.open(BytesIO(handle.read()))
        self.assertEqual((image.format, image.mode), ("PNG", "RGB"))
        self.assertEqual(image.getpixel((0, 0)), (255, 255, 255))

    def test_a_jpeg_is_accepted_and_stored_as_png(self):
        self.assertEqual(self.submit(upload(signature_bytes(fmt="JPEG"), "s.jpg", "image/jpeg")).status_code, 200)
        self.assertTrue(self.doc.signoffs.get().signature.name.endswith(".png"))


class ReturnTests(WorkflowBase):
    def submit_and_confirm(self):
        with mock.patch("apps.pdfgen.services.build_pdf.delay"):
            self.act(self.author, "submit")
            self.act(self.confirmer, "confirm")

    def test_the_reason_is_required(self):
        with mock.patch("apps.pdfgen.services.build_pdf.delay"):
            self.act(self.author, "submit")
        for reason in ("", "   ", None):
            response = self.act(self.confirmer, "return", reason=reason)
            self.assertEqual(response.status_code, 400, repr(reason))
            self.assertIn("reason", response.data)
        self.assertEqual(self.act(self.confirmer, "return", reason="x" * 1001).status_code, 400)
        self.assertEqual(Document.objects.get(pk=self.doc.pk).status, DocumentStatus.AWAITING_CONFIRMATION)

    def test_the_confirmer_returns_to_draft_and_signatures_are_cleared(self):
        with mock.patch("apps.pdfgen.services.build_pdf.delay"):
            self.act(self.author, "submit")
        stored = self.doc.signoffs.get().signature
        path = stored.path

        with self.captureOnCommitCallbacks(execute=True):
            response = self.act(self.confirmer, "return", reason="بند ۲ اصلاح شود")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], DocumentStatus.DRAFT)
        self.assertEqual(response.data["return_note"]["reason"], "بند ۲ اصلاح شود")
        self.assertEqual(response.data["return_note"]["by"], self.confirmer.full_name)

        self.assertEqual(self.doc.signoffs.count(), 0)
        import os
        self.assertFalse(os.path.exists(path), "the cleared signature file is removed")
        event = self.doc.events.last()
        self.assertEqual((event.kind, event.from_status, event.to_status, event.reason),
                         (DocumentEventKind.RETURNED, DocumentStatus.AWAITING_CONFIRMATION, DocumentStatus.DRAFT,
                          "بند ۲ اصلاح شود"))
        # The trail still says who had signed, although the sign-off rows are gone.
        self.assertEqual(self.doc.events.first().actor_name, self.author.full_name)

    def test_the_approver_returns_while_awaiting_approval(self):
        self.submit_and_confirm()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.act(self.approver, "return", reason="مغایرت با روش اجرایی")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.doc.signoffs.count(), 0)  # both signatures gone: the chain restarts
        self.assertEqual(self.doc.events.last().from_status, DocumentStatus.AWAITING_APPROVAL)

    def test_only_the_reviewer_of_the_current_step_may_return(self):
        with mock.patch("apps.pdfgen.services.build_pdf.delay"):
            self.act(self.author, "submit")
        chair = make_user("8000000025", AccessRoll.EMPLOYER, AccessLevel.LEVEL_2)  # a board member: no chart authority
        self.assertEqual(self.act(self.author, "return", reason="x").status_code, 403)     # a بخش's lead does not confirm
        self.assertEqual(self.act(chair, "return", reason="x").status_code, 403)           # no authority at all
        self.submit_and_confirm_more()
        self.assertEqual(self.act(self.confirmer2, "return", reason="x").status_code, 403)  # a confirmer: wrong step
        self.assertEqual(self.act(chair, "return", reason="x").status_code, 403)

    def submit_and_confirm_more(self):
        with mock.patch("apps.pdfgen.services.build_pdf.delay"):
            self.act(self.confirmer, "confirm")

    def test_a_draft_or_finished_document_cannot_be_returned(self):
        self.assertEqual(self.act(self.confirmer, "return", reason="x").data["code"], "wrong_status")
        done = self.run_chain()
        response = self.act(self.approver, "return", doc=done, reason="x")
        self.assertEqual((response.status_code, response.data["code"]), (409, "wrong_status"))

    def test_a_unit_lead_may_return_what_they_wrote_themselves(self):
        mine = make_doc(self.confirmer, title="سند واحد", owner_node=self.org.ai)
        with mock.patch("apps.pdfgen.services.build_pdf.delay"):
            self.act(self.confirmer, "submit", mine)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.act(self.confirmer, "return", mine, reason="بازنگری")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], DocumentStatus.DRAFT)

    def test_after_a_return_the_body_is_editable_again_and_the_chain_can_restart(self):
        with mock.patch("apps.pdfgen.services.build_pdf.delay"):
            self.act(self.author, "submit")
        # Locked while awaiting.
        locked = self.as_user(self.author).get(reverse("document-content", args=[self.doc.pk])).data
        self.assertFalse(locked["editable"])
        with self.captureOnCommitCallbacks(execute=True):
            self.act(self.confirmer, "return", reason="اصلاح شود")
        fresh = self.as_user(self.author).get(reverse("document-content", args=[self.doc.pk])).data
        self.assertTrue(fresh["editable"])
        self.assertEqual(fresh["document"]["return_note"]["reason"], "اصلاح شود")

        with mock.patch("apps.pdfgen.services.build_pdf.delay"), self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.act(self.author, "submit").status_code, 200)
            self.assertEqual(self.act(self.confirmer, "confirm").status_code, 200)
            self.assertEqual(self.act(self.approver, "approve").status_code, 200)
        final = self.as_user(self.author).get(reverse("document-detail", args=[self.doc.pk])).data
        self.assertEqual(final["status"], DocumentStatus.UNDER_CONTROL)
        self.assertIsNone(final["return_note"])
        kinds = [e.kind for e in self.doc.events.all()]
        self.assertEqual(kinds.count(DocumentEventKind.RETURNED), 1)
        self.assertEqual(kinds.count(DocumentEventKind.SUBMITTED), 2)

    def test_history_lists_the_trail_in_order(self):
        with mock.patch("apps.pdfgen.services.build_pdf.delay"):
            self.act(self.author, "submit")
        with self.captureOnCommitCallbacks(execute=True):
            self.act(self.confirmer, "return", reason="دلیل")
        data = self.as_user(self.author).get(reverse("document-history", args=[self.doc.pk])).data
        self.assertEqual([e["kind"] for e in data], ["submitted", "returned"])
        self.assertEqual(data[1]["reason"], "دلیل")
        self.assertEqual(data[1]["kind_label"], "مرجوع شد")
        self.assertEqual(data[1]["to_status_label"], "پیش نویس")
        self.assertNotIn("actor", data[1])


class SupersedeTests(WorkflowBase):
    def revise_and_approve(self, first):
        second = services.create_revision(user=self.author, document_id=first.pk)
        Document.objects.filter(pk=second.pk).update(content_saved_at=timezone.now())
        second.refresh_from_db()
        with mock.patch("apps.pdfgen.services.build_pdf.delay") as delay, self.captureOnCommitCallbacks(execute=True):
            for user, verb in ((self.author, "submit"), (self.confirmer, "confirm"), (self.approver, "approve")):
                self.assertEqual(self.act(user, verb, second).status_code, 200)
        return second, delay

    def test_approving_a_revision_obsoletes_the_previous_one(self):
        first = self.run_chain()
        second, _ = self.revise_and_approve(first)
        first.refresh_from_db()
        self.assertEqual(first.status, DocumentStatus.OBSOLETE)
        self.assertEqual(Document.objects.get(pk=second.pk).status, DocumentStatus.UNDER_CONTROL)
        event = first.events.last()
        self.assertEqual((event.kind, event.from_status, event.to_status),
                         (DocumentEventKind.SUPERSEDED, DocumentStatus.UNDER_CONTROL, DocumentStatus.OBSOLETE))
        self.assertIn(second.full_code, event.reason)
        self.assertEqual(event.actor_id, self.approver.pk)

    def test_the_previous_revision_stays_valid_until_the_new_one_is_approved(self):
        first = self.run_chain()
        second = services.create_revision(user=self.author, document_id=first.pk)
        Document.objects.filter(pk=second.pk).update(content_saved_at=timezone.now())
        with mock.patch("apps.pdfgen.services.build_pdf.delay"):
            self.act(self.author, "submit", second)
            self.act(self.confirmer, "confirm", second)
        first.refresh_from_db()
        self.assertEqual(first.status, DocumentStatus.UNDER_CONTROL)

    def test_only_the_new_pdf_is_built_when_the_old_one_was_never_built(self):
        first = self.run_chain()
        PdfBuild.objects.filter(document=first).delete()
        second, delay = self.revise_and_approve(first)
        self.assertEqual(delay.call_count, 1)
        self.assertTrue(PdfBuild.objects.filter(document=second, kind=PdfKind.OFFICIAL).exists())
        self.assertFalse(PdfBuild.objects.filter(document=first).exists())

    def test_the_superseded_pdf_is_rebuilt_so_it_stops_saying_valid(self):
        first = self.run_chain()
        PdfBuild.objects.filter(document=first).update(
            status=PdfStatus.READY, path="pdfs/x.pdf", built_at=timezone.now())
        second, delay = self.revise_and_approve(first)
        self.assertEqual(delay.call_count, 2)
        rebuilt = PdfBuild.objects.get(document=first, kind=PdfKind.OFFICIAL)
        self.assertEqual(rebuilt.status, PdfStatus.BUILDING)
        self.assertEqual(rebuilt.requested_by_id, self.approver.pk)

    def test_a_running_build_of_the_old_revision_does_not_fail_the_approval(self):
        first = self.run_chain()
        PdfBuild.objects.filter(document=first).update(status=PdfStatus.BUILDING, requested_at=timezone.now())
        second, _ = self.revise_and_approve(first)
        self.assertEqual(Document.objects.get(pk=second.pk).status, DocumentStatus.UNDER_CONTROL)
        first.refresh_from_db()
        self.assertEqual(first.status, DocumentStatus.OBSOLETE)

    def test_an_already_obsolete_previous_revision_is_left_alone(self):
        first = self.run_chain()
        Document.objects.filter(pk=first.pk).update(status=DocumentStatus.OBSOLETE)
        before = first.events.count()
        self.revise_and_approve(first)
        self.assertEqual(first.events.count(), before)


class RegisterWorkflowFlagsTests(WorkflowBase):
    def flags(self, user, doc=None):
        rows = self.as_user(user).get(reverse("document-list")).data["results"]
        return {r["id"]: r["workflow"] for r in rows}[(doc or self.doc).pk]

    def test_flags_follow_status_and_the_chart(self):
        chair = make_user("8000000026", AccessRoll.EMPLOYER, AccessLevel.LEVEL_2)
        self.assertEqual(self.flags(self.author), {"step": "submit", "can_act": True, "can_return": False})
        self.assertFalse(self.flags(chair)["can_act"])  # leads nothing

        with mock.patch("apps.pdfgen.services.build_pdf.delay"):
            self.act(self.author, "submit")
        self.assertEqual(self.flags(self.confirmer), {"step": "confirm", "can_act": True, "can_return": True})
        self.assertFalse(self.flags(self.author)["can_act"])   # a بخش's lead does not confirm
        self.assertFalse(self.flags(chair)["can_act"])
        self.assertTrue(self.flags(self.approver)["can_act"])  # the مدیر عامل may take any step

        with mock.patch("apps.pdfgen.services.build_pdf.delay"):
            self.act(self.confirmer, "confirm")
        self.assertTrue(self.flags(self.approver)["can_act"])
        self.assertFalse(self.flags(self.confirmer)["can_act"])  # only the مدیر عامل approves

    def test_a_lead_elsewhere_gets_no_button_on_this_document(self):
        elsewhere = make_user("8000000027", AccessRoll.GUILD)
        test_support.lead_of(elsewhere, self.org.llm)
        self.assertFalse(self.flags(elsewhere)["can_act"])
        self.assertFalse(self.flags(elsewhere)["can_return"])

    def test_the_register_says_who_may_edit_and_revise(self):
        elsewhere = make_user("8000000028", AccessRoll.GUILD)
        test_support.lead_of(elsewhere, self.org.llm)

        def row(user):
            rows = self.as_user(user).get(reverse("document-list")).data["results"]
            return {r["id"]: r for r in rows}[self.doc.pk]

        self.assertTrue(row(self.author)["can_edit"])
        self.assertTrue(row(self.confirmer)["can_edit"])  # the واحد's lead writes its بخش's documents too
        self.assertTrue(row(self.approver)["can_edit"])
        self.assertFalse(row(elsewhere)["can_edit"])

    def test_a_draft_without_a_saved_body_has_no_step(self):
        empty = make_doc(self.author, title="خالی", saved=False)
        self.assertIsNone(self.flags(self.author, empty)["step"])

    def test_finished_documents_have_no_step(self):
        done = self.run_chain()
        self.assertIsNone(self.flags(self.approver, done)["step"])

    def test_the_list_costs_no_extra_queries(self):
        # count + page + sign-offs + responsibility sections, and the person's lead nodes (one query, whatever the
        # number of rows — Phase 14).
        self.run_chain()
        make_doc(self.author, title="یکی دیگر")
        with self.assertNumQueries(5):
            self.as_user(self.confirmer).get(reverse("document-list"))

    def test_next_step_for_handles_anonymous_and_missing_users(self):
        self.assertFalse(workflow.next_step_for(self.doc, None)["can_act"])


@override_settings(MEDIA_ROOT=MEDIA, CACHES=LOCMEM, RATELIMIT_ENABLE=False)
class ConcurrentWorkflowTests(TransactionTestCase):
    """Two reviewers acting on one document at the same instant: one wins."""

    def setUp(self):
        org = test_support.ensure_org()
        self.author = make_user("8100000001", AccessRoll.GUILD)
        test_support.lead_of(self.author, org.rag)
        self.c1 = make_user("8100000002", AccessRoll.HEADQUARTERS)
        self.c2 = make_user("8100000003", AccessRoll.HEADQUARTERS)
        test_support.lead_of(self.c1, org.ai)
        test_support.lead_of(self.c2, org.ai)
        self.doc = make_doc(self.author)
        with mock.patch("apps.pdfgen.services.build_pdf.delay"):
            workflow.submit(user=self.author, document_id=self.doc.pk,
                            signature=SimpleUploadedFile("s.png", signature_bytes(), "image/png"))

    def race(self, calls):
        barrier = threading.Barrier(len(calls))
        outcomes = []

        def run(call):
            try:
                barrier.wait()
                call()
                outcomes.append("ok")
            except ConflictError as error:
                outcomes.append(error.payload["code"])
            except PermissionDenied:
                outcomes.append("denied")
            finally:
                connection.close()

        threads = [threading.Thread(target=run, args=(c,)) for c in calls]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return sorted(outcomes)

    @skipUnlessDBFeature("has_select_for_update")
    def test_two_simultaneous_confirms_have_exactly_one_winner(self):
        def confirm(user):
            return lambda: workflow.confirm(
                user=user, document_id=self.doc.pk,
                signature=SimpleUploadedFile("s.png", signature_bytes(), "image/png"))

        self.assertEqual(self.race([confirm(self.c1), confirm(self.c2)]), ["ok", "wrong_status"])
        self.assertEqual(SignOff.objects.filter(document=self.doc, role=SignOffRole.CONFIRMER).count(), 1)
        self.assertEqual(self.doc.events.filter(kind=DocumentEventKind.CONFIRMED).count(), 1)

    @skipUnlessDBFeature("has_select_for_update")
    def test_a_confirm_racing_a_return_leaves_a_consistent_document(self):
        confirm = lambda: workflow.confirm(
            user=self.c1, document_id=self.doc.pk,
            signature=SimpleUploadedFile("s.png", signature_bytes(), "image/png"))
        ret = lambda: workflow.return_document(user=self.c2, document_id=self.doc.pk, reason="دلیل")
        outcomes = self.race([confirm, ret])
        document = Document.objects.get(pk=self.doc.pk)
        signoffs = SignOff.objects.filter(document=document).count()
        # Exactly two coherent worlds. The return won: back to DRAFT with no
        # signatures, and the confirm found a DRAFT. Or the confirm won: awaiting
        # approval with two signatures, and the return then hit the approver-only rule (a unit's lead does not approve).
        if document.status == DocumentStatus.DRAFT:
            self.assertEqual(outcomes, ["ok", "wrong_status"])
            self.assertEqual(signoffs, 0)
        else:
            self.assertEqual(outcomes, ["denied", "ok"])
            self.assertEqual((document.status, signoffs), (DocumentStatus.AWAITING_APPROVAL, 2))


@override_settings(CACHES=LOCMEM, RATELIMIT_ENABLE=False)
class VerifyTests(TestCase):
    def setUp(self):
        cache.clear()
        self.author = make_user("8200000001", AccessRoll.GUILD)
        self.client = APIClient()

    def make_under_control(self, **kwargs):
        doc = make_doc(self.author, **kwargs)
        Document.objects.filter(pk=doc.pk).update(status=DocumentStatus.UNDER_CONTROL)
        doc.refresh_from_db()
        SignOff.objects.create(document=doc, role=SignOffRole.CREATER, name="علی رضایی", position="کارشناس",
                               signed_date=date(2025, 4, 8))
        SignOff.objects.create(document=doc, role=SignOffRole.APPROVER, name="مدیر عامل", position="مدیر",
                               signed_date=date(2025, 4, 10))
        return doc

    def get(self, code):
        return self.client.get(reverse("verify", args=[code]))

    def test_a_document_under_control_is_valid(self):
        doc = self.make_under_control(title="روش کنترل")
        response = self.get(doc.full_code)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual((data["found"], data["state"], data["state_label"]), (True, "valid", "معتبر"))
        self.assertEqual((data["title"], data["full_code"], data["revision_display"]), ("روش کنترل", "PR-01-01", "01"))
        self.assertEqual([s["name"] for s in data["signers"]], ["علی رضایی", "مدیر عامل"])  # tadvin, then tasvib
        self.assertIsNone(data["current_revision"])
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_lookup_is_case_insensitive_and_tolerates_whitespace(self):
        doc = self.make_under_control()
        self.assertEqual(self.get(doc.full_code.lower()).status_code, 200)
        self.assertEqual(self.get(f" {doc.full_code} ").status_code, 200)

    def test_an_obsolete_revision_says_so_and_points_at_the_current_one(self):
        first = self.make_under_control()
        Document.objects.filter(pk=first.pk).update(status=DocumentStatus.OBSOLETE)
        second = Document.objects.create(
            category=DocumentCategory.INSIDE, title=first.title, group=first.group, number=first.number, revision=2,
            status=DocumentStatus.UNDER_CONTROL, previous_revision=first, created_by=self.author)
        data = self.get(first.full_code).json()
        self.assertEqual((data["state"], data["state_label"]), ("obsolete", "منسوخ"))
        self.assertEqual(data["current_revision"], {"full_code": second.full_code, "revision_display": "02"})
        self.assertEqual(self.get(second.full_code).json()["state"], "valid")

    def test_an_obsolete_revision_with_no_current_one_has_no_pointer(self):
        first = self.make_under_control()
        Document.objects.filter(pk=first.pk).update(status=DocumentStatus.OBSOLETE)
        self.assertIsNone(self.get(first.full_code).json()["current_revision"])

    def test_an_unapproved_document_discloses_nothing_but_that_it_is_not_valid(self):
        drafts = []
        for n, status in enumerate((DocumentStatus.DRAFT, DocumentStatus.AWAITING_CONFIRMATION, DocumentStatus.AWAITING_APPROVAL)):
            doc = make_doc(self.author, title=f"محرمانه {n}")
            Document.objects.filter(pk=doc.pk).update(status=status)
            drafts.append(doc)
        for doc in drafts:
            data = self.get(doc.full_code).json()
            self.assertEqual((data["found"], data["state"], data["state_label"]), (True, "pending", "در دست بررسی"))
            self.assertEqual(set(data), {"found", "full_code", "revision_display", "state", "state_label", "message"})

    def test_unknown_and_malformed_codes_are_404(self):
        for code in ("PR-99-01", "XX-01-01", "PR-01", "PR-01-01-01", "PR-AA-01", "..%2F", "PR-01-00"):
            response = self.get(code)
            self.assertEqual(response.status_code, 404, code)
            self.assertFalse(response.json()["found"])

    def test_no_internal_identifiers_leak(self):
        doc = self.make_under_control()
        data = self.get(doc.full_code).json()
        flat = str(data)
        for forbidden in ("created_by", "'id'", "national_code", "signature", "content_saved_at"):
            self.assertNotIn(forbidden, flat)

    def test_it_is_public_and_ignores_credentials(self):
        doc = self.make_under_control()
        stale = APIClient()
        stale.cookies["access_token"] = "garbage.token.value"  # an expired/invalid cookie must not 401 a scanner
        self.assertEqual(stale.get(reverse("verify", args=[doc.full_code])).status_code, 200)

    @override_settings(RATELIMIT_ENABLE=True, VERIFY_RATELIMIT_RATE="3/m")
    def test_it_is_rate_limited_per_ip(self):
        doc = self.make_under_control()
        codes = [self.get(doc.full_code).status_code for _ in range(5)]
        self.assertEqual(codes, [200, 200, 200, 403, 403])


class ManagingDirectorTests(WorkflowBase):
    """The مدیر عامل (کارفرمایی لول ۱): the only approver, and he may also write and confirm anything —
    including, since 2026-09-30, what he wrote or confirmed himself."""

    def setUp(self):
        super().setUp()
        self.ceo = make_user("8000000010", AccessRoll.EMPLOYER, AccessLevel.LEVEL_1)

    def test_can_take_every_step_anywhere_even_on_his_own_document(self):
        mine = make_doc(self.ceo, title="سند مدیر عامل")
        elsewhere = make_doc(self.author, title="جای دیگر", owner_node=self.org.deals)
        with mock.patch("apps.pdfgen.services.build_pdf.delay"), self.captureOnCommitCallbacks(execute=True):
            for verb in ("submit", "confirm", "approve"):
                self.assertEqual(self.act(self.ceo, verb, mine).status_code, 200, verb)
            self.assertEqual(self.act(self.ceo, "submit", elsewhere).status_code, 200)
        self.assertEqual(Document.objects.get(pk=mine.pk).status, DocumentStatus.UNDER_CONTROL)
        self.assertEqual({s.signed_by_id for s in SignOff.objects.filter(document=mine)}, {self.ceo.pk})

    def test_can_approve_what_others_wrote_and_confirmed(self):
        with mock.patch("apps.pdfgen.services.build_pdf.delay"), self.captureOnCommitCallbacks(execute=True):
            self.act(self.author, "submit")
            self.act(self.confirmer, "confirm")
            self.assertEqual(self.act(self.ceo, "approve").status_code, 200)

    def test_can_return_a_document_at_either_review_step(self):
        doc = make_doc(self.author, title="برای مرجوع")
        with mock.patch("apps.pdfgen.services.build_pdf.delay"):
            self.act(self.author, "submit", doc)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.act(self.ceo, "return", doc, reason="اصلاح شود").status_code, 200)  # as confirmer
        with mock.patch("apps.pdfgen.services.build_pdf.delay"):
            self.act(self.author, "submit", doc)
            self.act(self.confirmer, "confirm", doc)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.act(self.ceo, "return", doc, reason="دوباره").status_code, 200)     # as approver

    def test_the_register_offers_him_the_right_buttons(self):
        draft = make_doc(self.ceo, title="پیش‌نویس او")
        rows = {r["id"]: r["workflow"] for r in self.as_user(self.ceo).get(reverse("document-list")).data["results"]}
        self.assertEqual(rows[draft.pk], {"step": "submit", "can_act": True, "can_return": False})
        with mock.patch("apps.pdfgen.services.build_pdf.delay"):
            self.act(self.author, "submit", self.doc)
        rows = {r["id"]: r["workflow"] for r in self.as_user(self.ceo).get(reverse("document-list")).data["results"]}
        self.assertEqual(rows[self.doc.pk], {"step": "confirm", "can_act": True, "can_return": True})

    def test_can_manage_personnel_print_and_create_a_document_anywhere(self):
        client = self.as_user(self.ceo)
        self.assertEqual(client.get(reverse("personnel-list")).status_code, 200)
        self.assertEqual(client.post(reverse("document-list"), {
            "category": DocumentCategory.INSIDE, "title": "ساختهٔ مدیر عامل", "group": DocumentGroup.FORM,
            "owner_node": self.org.root.pk}, format="json").status_code, 201)
        self.assertIn("print_document", client.get(reverse("auth-me")).data["capabilities"])
        self.assertEqual(set(client.get(reverse("auth-me")).data["capabilities"]), set(Capability.values))

    def test_a_document_with_no_owner_node_is_his_alone(self):
        orphan = make_doc(self.author, title="یتیم")
        Document.objects.filter(pk=orphan.pk).update(owner_node=None)
        self.assertEqual(self.act(self.author, "submit", orphan).status_code, 403)
        self.assertEqual(self.act(self.confirmer, "submit", orphan).status_code, 403)
        with mock.patch("apps.pdfgen.services.build_pdf.delay"):
            self.assertEqual(self.act(self.ceo, "submit", orphan).status_code, 200)

    def test_a_board_member_acts_on_nothing(self):
        # رئیس هیئت مدیره (کارفرمایی لول ۲): the roll no longer approves — only the مدیر عامل does.
        chair = make_user("8000000011", AccessRoll.EMPLOYER, AccessLevel.LEVEL_2)
        self.assertEqual(self.act(chair, "submit").status_code, 403)
        self.assertEqual(self.as_user(chair).post(reverse("document-list"), {
            "category": DocumentCategory.INSIDE, "title": "نباید", "group": DocumentGroup.FORM,
            "owner_node": self.org.root.pk}, format="json").status_code, 403)
        self.assertNotIn("approve_document", self.as_user(chair).get(reverse("auth-me")).data["capabilities"])
