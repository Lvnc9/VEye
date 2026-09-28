"""The designer's live paper (Phase 12): POST /documents/{id}/live-preview/."""
import shutil
import tempfile
from unittest import mock

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import AccessLevel, AccessRoll
from apps.core.constants import DocumentGroup, DocumentStatus, SectionType
from apps.documents.models import Document, DocumentFile, Section
from apps.documents.tests import make_user, new_doc
from apps.pdfgen import live_preview, render

from . import cases as C
from .helpers import LOCMEM_CACHE

MEDIA = tempfile.mkdtemp(prefix="veye-live-media-")


def tearDownModule():
    shutil.rmtree(MEDIA, ignore_errors=True)


def short(*lines, section_id=None):
    return {"id": section_id, "type": SectionType.SHORT_EXPLANATION, "lines": list(lines)}


@override_settings(MEDIA_ROOT=MEDIA, FRONTEND_BASE_URL=C.FRONTEND, CACHES=LOCMEM_CACHE, RATELIMIT_ENABLE=False)
class LivePreviewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.author = make_user("6100000001", AccessRoll.GUILD, AccessLevel.LEVEL_3)
        self.doc = new_doc(self.author, "روش پیش‌نمایش", DocumentGroup.PROCEDURE)
        self.client = APIClient()
        self.client.force_authenticate(self.author)

    def post(self, body=None, known=None, doc=None):
        payload = {}
        if body is not None:
            payload["body"] = body
        if known is not None:
            payload["known_hashes"] = known
        return self.client.post(reverse("live-preview", kwargs={"document_id": (doc or self.doc).pk}), payload, format="json")

    def body(self, sections, version=None):
        self.doc.refresh_from_db()
        return {
            "base_version": self.doc.content_version if version is None else version,
            "footnote1": "",
            "footnote2": "",
            "sections": sections,
        }

    def test_unsaved_edits_are_drawn_but_never_stored(self):
        seen = {}
        real = render.render

        def spy(document_id, *, preview):
            seen["lines"] = [s.content.get("lines") for s in Section.objects.filter(document_id=document_id)]
            seen["preview"] = preview
            return real(document_id, preview=preview)

        with mock.patch.object(live_preview.render, "render", side_effect=spy):
            response = self.post(self.body([short("خط تازه", "هنوز ذخیره نشده")]))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(seen["lines"], [["خط تازه", "هنوز ذخیره نشده"]])
        self.assertFalse(seen["preview"])  # the paper as it prints, no watermark
        self.assertEqual(response.data["page_count"], 2)  # the owner's layout: cover page + body
        self.assertTrue(all(page["image"].startswith("data:image/png;base64,") for page in response.data["pages"]))
        # Nothing was kept.
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.sections.count(), 0)
        self.assertEqual(self.doc.content_version, 0)
        self.assertIsNone(self.doc.content_saved_at)
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_without_a_body_the_stored_document_is_drawn(self):
        self.assertEqual(self.post().status_code, 200)

    def test_a_stale_version_is_a_conflict_like_a_save(self):
        response = self.post(self.body([short("x")], version=7))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "version_conflict")

    def test_a_locked_document_refuses_edits_but_shows_its_paper(self):
        Document.objects.filter(pk=self.doc.pk).update(status=DocumentStatus.UNDER_CONTROL)
        self.assertEqual(self.post(self.body([short("x")])).data["code"], "content_locked")
        self.assertEqual(self.post().status_code, 200)

    def test_someone_who_cannot_author_sees_only_the_stored_paper(self):
        reviewer = make_user("6100000002", AccessRoll.EMPLOYER, AccessLevel.LEVEL_2)  # approver-only
        self.client.force_authenticate(reviewer)
        self.assertEqual(self.post(self.body([short("x")])).status_code, 403)
        self.assertEqual(self.post().status_code, 200)

    def test_invalid_edits_answer_like_a_save(self):
        response = self.post(self.body([{"type": "Nope"}]))
        self.assertEqual(response.status_code, 400)

    def test_pages_the_client_already_has_are_not_sent_again(self):
        first = self.post(self.body([short("الف")])).data["pages"]
        again = self.post(self.body([short("الف")]), known=[page["hash"] for page in first]).data["pages"]
        self.assertEqual([p["hash"] for p in again], [p["hash"] for p in first])
        self.assertTrue(all("image" not in page for page in again))
        changed = self.post(self.body([short("ب")]), known=[page["hash"] for page in first]).data["pages"]
        self.assertTrue(any("image" in page for page in changed))  # the body page changed

    def test_long_documents_are_cut_at_the_page_cap(self):
        with mock.patch.object(live_preview, "MAX_PAGES", 1):
            data = self.post(self.body([short("x")])).data
        self.assertEqual(len(data["pages"]), 1)
        self.assertEqual(data["page_count"], 2)
        self.assertTrue(data["truncated"])

    def test_a_file_left_out_of_the_preview_is_not_deleted(self):
        upload = SimpleUploadedFile("note.pdf", b"%PDF-1.4 kept", content_type="application/pdf")
        created = self.client.post(reverse("document-upload-file", kwargs={"pk": self.doc.pk}), {"file": upload}, format="multipart")
        self.assertEqual(created.status_code, 201)
        record = DocumentFile.objects.get(pk=created.data["id"])
        path = record.file.path
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.assertEqual(self.post(self.body([short("بدون فایل")])).status_code, 200)
        self.assertEqual(callbacks, [])  # the rolled-back save queued no deletion
        self.assertTrue(DocumentFile.objects.filter(pk=record.pk).exists())
        with open(path, "rb") as handle:
            self.assertEqual(handle.read(), b"%PDF-1.4 kept")

    def test_a_form_goes_through_the_form_renderer(self):
        form = new_doc(self.author, "فرم پیش‌نمایش", DocumentGroup.FORM)
        body = {
            "base_version": 0,
            "footnote1": "",
            "footnote2": "",
            "form_settings": {"orientation": "landscape"},
            "sections": [{"id": None, "type": SectionType.FORM_ELEMENT, "kind": "heading", "text": "مشخصات"}],
        }
        data = self.post(body, doc=form).data
        self.assertEqual(data["page_count"], 1)  # the compact form layout starts on page 1
        form.refresh_from_db()
        self.assertEqual(form.form_settings["orientation"], "portrait")  # not kept

    @override_settings(RATELIMIT_ENABLE=True, LIVE_PREVIEW_RATELIMIT_RATE="2/m")
    def test_the_rate_limit_answers_429_in_persian(self):
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(self.post().status_code, 200)
        response = self.post()
        self.assertEqual(response.status_code, 429)
        self.assertIn("صبر کنید", str(response.data["detail"]))

    def test_an_unknown_document(self):
        response = self.client.post(reverse("live-preview", kwargs={"document_id": 999999}), {}, format="json")
        self.assertEqual(response.status_code, 404)
