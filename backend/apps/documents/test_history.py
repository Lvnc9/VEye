"""The History screen's two read-only endpoints (Phase 6)."""
from datetime import date, timedelta

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AccessLevel, AccessRoll, User
from apps.core.constants import (
    DocumentCategory,
    DocumentEventKind,
    DocumentGroup,
    DocumentStatus,
    SignOffRole,
)
from apps.pdfgen.models import PdfBuild, PdfKind, PdfStatus

from .models import Document, DocumentEvent, SignOff

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "veye-history-tests"}}


def make_doc(author, *, number, revision=1, group=DocumentGroup.PROCEDURE, title="سند", status=DocumentStatus.UNDER_CONTROL,
             category=DocumentCategory.INSIDE, previous=None):
    return Document.objects.create(
        category=category, title=title, group=group, number=number, revision=revision, status=status,
        previous_revision=previous, created_by=author, content_saved_at=timezone.now(),
    )


def event(document, kind, *, actor="علی رضایی", title="کارشناس", reason="", ago=timedelta(0), to=DocumentStatus.UNDER_CONTROL):
    e = DocumentEvent.objects.create(
        document=document, kind=kind, from_status=DocumentStatus.DRAFT, to_status=to,
        actor_name=actor, actor_title=title, reason=reason)
    DocumentEvent.objects.filter(pk=e.pk).update(created_at=timezone.now() - ago)
    return e


@override_settings(CACHES=LOCMEM)
class HistoryBase(TestCase):
    def setUp(self):
        cache.clear()
        self.author = User.objects.create_user(
            national_code="8300000001", password="pw-for-tests-123", full_name="نویسنده",
            access_roll=AccessRoll.GUILD, access_level=AccessLevel.LEVEL_2)
        self.client = APIClient()
        self.client.force_authenticate(self.author)

    def get(self, name, **params):
        return self.client.get(reverse(name), params)


class RevisionHistoryTests(HistoryBase):
    def setUp(self):
        super().setUp()
        self.pr1_r1 = make_doc(self.author, number=1, revision=1, title="روش کنترل", status=DocumentStatus.OBSOLETE)
        self.pr1_r2 = make_doc(self.author, number=1, revision=2, title="روش کنترل", previous=self.pr1_r1)
        self.pr2 = make_doc(self.author, number=2, title="روش دوم", status=DocumentStatus.DRAFT,
                            category=DocumentCategory.OUTSIDE)
        self.po1 = make_doc(self.author, number=1, group=DocumentGroup.POSTER, title="پوستر ایمنی")

    def codes(self, **params):
        return [r["full_code"] for r in self.get("history-revisions", **params).data["results"]]

    def test_lists_every_revision_by_family_newest_revision_first(self):
        self.assertEqual(self.codes(), ["PO-01-01", "PR-01-02", "PR-01-01", "PR-02-01"])

    def test_families_sort_by_the_printed_code_not_the_group_name(self):
        # Group names sort FORM < INSTRUCTION < POSTER < PROCEDURE, i.e. FR, WI, PO, PR;
        # the codes people read sort FR, PO, PR, WI.
        make_doc(self.author, number=1, group=DocumentGroup.FORM, title="فرم")
        make_doc(self.author, number=1, group=DocumentGroup.INSTRUCTION, title="دستور")
        self.assertEqual(self.codes(), ["FR-01-01", "PO-01-01", "PR-01-02", "PR-01-01", "PR-02-01", "WI-01-01"])

    def test_requires_authentication(self):
        self.assertEqual(APIClient().get(reverse("history-revisions")).status_code, 401)

    def test_row_carries_status_signers_and_no_internal_ids_beyond_the_row(self):
        SignOff.objects.create(document=self.pr1_r2, role=SignOffRole.CREATER, name="علی رضایی", position="کارشناس",
                               signed_date=date(2025, 4, 8))
        SignOff.objects.create(document=self.pr1_r2, role=SignOffRole.APPROVER, name="مدیر", position="مدیر عامل",
                               signed_date=date(2025, 4, 10))
        row = next(r for r in self.get("history-revisions").data["results"] if r["full_code"] == "PR-01-02")
        self.assertEqual((row["status"], row["status_label"], row["revision_display"]), ("UNDER_CONTROL", "تحت کنترل", "02"))
        self.assertEqual(row["signoffs"]["creater"]["name"], "علی رضایی")
        self.assertEqual(str(row["signoffs"]["approver"]["signed_date"]), "2025-04-10")
        self.assertIsNone(row["signoffs"]["confirmer"])
        self.assertNotIn("created_by", row)

    def test_family_filter_returns_one_documents_whole_chain(self):
        self.assertEqual(self.codes(family="PR-01"), ["PR-01-02", "PR-01-01"])
        self.assertEqual(self.codes(family="pr-01"), ["PR-01-02", "PR-01-01"])  # case-insensitive
        self.assertEqual(self.codes(family="PO-01"), ["PO-01-01"])

    def test_bad_or_unknown_family_matches_nothing(self):
        for family in ("PR-99", "XX-01", "PR-01-01", "nonsense", "PR-"):
            self.assertEqual(self.codes(family=family), [], family)

    def test_filters_by_group_category_and_status(self):
        self.assertEqual(self.codes(group="POSTER"), ["PO-01-01"])
        self.assertEqual(self.codes(category="OUTSIDE"), ["PR-02-01"])
        self.assertEqual(self.codes(status="OBSOLETE"), ["PR-01-01"])
        self.assertEqual(self.codes(status="NOPE"), [])  # a stale link matches nothing, not everything

    def test_search_matches_title_and_the_printed_code_with_persian_normalisation(self):
        self.assertEqual(self.codes(search="پوستر"), ["PO-01-01"])
        self.assertEqual(self.codes(search="PR-01-02"), ["PR-01-02"])  # the revision part matches
        Document.objects.filter(pk=self.pr2.pk).update(title="بازرسی")  # titles are stored with Persian yeh
        self.assertEqual(self.codes(search="بازرسي"), ["PR-02-01"])  # a term typed with Arabic yeh still finds it
        # …and a group label matches, exactly as in the register.
        self.assertEqual(self.codes(search="اجرایی"), ["PR-01-02", "PR-01-01", "PR-02-01"])

    def test_paginates(self):
        data = self.get("history-revisions", page_size=2).data
        self.assertEqual((data["count"], len(data["results"])), (4, 2))
        self.assertIsNotNone(data["next"])

    def test_reports_the_issued_pdf_state_without_touching_pdfs(self):
        PdfBuild.objects.create(document=self.pr1_r2, kind=PdfKind.OFFICIAL, status=PdfStatus.READY,
                                path="pdfs/x.pdf", built_at=timezone.now())
        PdfBuild.objects.create(document=self.pr1_r1, kind=PdfKind.PREVIEW, status=PdfStatus.READY,
                                path="pdf_previews/y.pdf", built_at=timezone.now())  # a preview is not the issued PDF
        rows = {r["full_code"]: r for r in self.get("history-revisions").data["results"]}
        self.assertEqual(rows["PR-01-02"]["pdf_status"], "ready")
        self.assertIsNotNone(rows["PR-01-02"]["pdf_built_at"])
        self.assertEqual(rows["PR-01-01"]["pdf_status"], "none")

    def test_no_query_per_row(self):
        for n in range(3, 12):
            doc = make_doc(self.author, number=n, title=f"سند {n}")
            SignOff.objects.create(document=doc, role=SignOffRole.CREATER, name="ن", position="س")
        with self.assertNumQueries(3):  # count + page + sign-offs
            self.get("history-revisions", page_size=50)


class ActivityFeedTests(HistoryBase):
    def setUp(self):
        super().setUp()
        self.a = make_doc(self.author, number=1, title="روش الف")
        self.b = make_doc(self.author, number=2, title="روش ب", status=DocumentStatus.DRAFT)
        self.e1 = event(self.a, DocumentEventKind.SUBMITTED, ago=timedelta(days=40), actor="علی رضایی")
        self.e2 = event(self.a, DocumentEventKind.APPROVED, ago=timedelta(days=2), actor="مدیر عامل")
        self.e3 = event(self.b, DocumentEventKind.RETURNED, ago=timedelta(hours=1), actor="محمد شجراوی",
                        reason="بند ۲ اصلاح شود", to=DocumentStatus.DRAFT)

    def ids(self, **params):
        return [e["id"] for e in self.get("history-activity", **params).data["results"]]

    def test_newest_first_across_documents(self):
        self.assertEqual(self.ids(), [self.e3.id, self.e2.id, self.e1.id])

    def test_requires_authentication(self):
        self.assertEqual(APIClient().get(reverse("history-activity")).status_code, 401)

    def test_event_carries_document_actor_and_reason_but_no_user_id(self):
        row = self.get("history-activity").data["results"][0]
        self.assertEqual(row["kind"], "returned")
        self.assertEqual(row["kind_label"], "مرجوع شد")
        self.assertEqual(row["reason"], "بند ۲ اصلاح شود")
        self.assertEqual(row["actor_name"], "محمد شجراوی")
        self.assertEqual(row["to_status_label"], "پیش نویس")
        self.assertEqual(row["document"], {"id": self.b.id, "full_code": "PR-02-01", "title": "روش ب"})
        self.assertNotIn("actor", row)

    def test_filters(self):
        self.assertEqual(self.ids(kind="approved"), [self.e2.id])
        self.assertEqual(self.ids(kind="nope"), [])
        self.assertEqual(self.ids(document=self.a.id), [self.e2.id, self.e1.id])
        self.assertEqual(self.ids(document="abc"), [])
        self.assertEqual(self.ids(q="PR-02"), [self.e3.id])
        self.assertEqual(self.ids(q="روش الف"), [self.e2.id, self.e1.id])
        self.assertEqual(self.ids(actor="شجراوی"), [self.e3.id])

    def test_days_window(self):
        self.assertEqual(self.ids(days=7), [self.e3.id, self.e2.id])
        self.assertEqual(self.ids(days=365), [self.e3.id, self.e2.id, self.e1.id])
        for bad in ("0", "-3", "x"):
            self.assertEqual(self.ids(days=bad), [], bad)

    def test_a_real_workflow_shows_up_in_the_feed(self):
        # Wired to the actual services, not hand-made rows.
        from unittest import mock
        from io import BytesIO
        from PIL import Image, ImageDraw
        from django.core.files.uploadedfile import SimpleUploadedFile
        from . import workflow

        image = Image.new("RGB", (200, 90), (255, 255, 255))
        ImageDraw.Draw(image).line([(10, 60), (100, 20), (180, 70)], fill=(0, 0, 100), width=4)
        buffer = BytesIO(); image.save(buffer, "PNG")
        with mock.patch("apps.pdfgen.services.build_pdf.delay"):
            workflow.submit(user=self.author, document_id=self.b.pk,
                            signature=SimpleUploadedFile("s.png", buffer.getvalue(), "image/png"))
        newest = self.get("history-activity").data["results"][0]
        self.assertEqual((newest["kind"], newest["actor_name"]), ("submitted", self.author.full_name))

    def test_paginates_and_costs_two_queries_plus_count(self):
        for n in range(20):
            event(self.a, DocumentEventKind.CONFIRMED)
        with self.assertNumQueries(2):  # count + page (document joined)
            data = self.get("history-activity", page_size=10).data
        self.assertEqual(len(data["results"]), 10)
