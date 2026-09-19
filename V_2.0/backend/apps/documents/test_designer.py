"""Phase 3: the document designer — body content, files, logo, revisions."""
import io
import os
import shutil
import tempfile
import threading
from datetime import date

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.db.models import ProtectedError
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import AccessLevel, AccessRoll
from apps.core.constants import DocumentGroup, DocumentStatus, ResponsibilityRole
from apps.core.exceptions import ConflictError

from . import content, services
from .models import (
    AttachmentReference,
    ChangeTableRow,
    Document,
    DocumentFile,
    ResponsibilityRow,
    Section,
)
from .tests import LOCMEM_CACHE, finalize, make_user, new_doc

SHORT = "Short Explanation"
LONG = "Long Explanation"
RESP = "Responsibilities"
CHANGES = "Changes Table"
ATTACH = "Attachment"


# -- payload builders --------------------------------------------------------


def short(*lines, **extra):
    return {"type": SHORT, "lines": list(lines), **extra}


def long_block(heading="", body="", extra_boxes=(), file_ids=(), **extra):
    return {
        "type": LONG,
        "heading": heading,
        "body": body,
        "extra_boxes": list(extra_boxes),
        "file_ids": list(file_ids),
        **extra,
    }


def resp(overrides=None, notes=(), **extra):
    """A Responsibilities block with all four roles; `overrides` maps a role to
    the fields to set on it."""
    overrides = overrides or {}
    roles = [
        {"role": role, "post": "", "supervisor": "", "text": "", **overrides.get(role, {})}
        for role in ResponsibilityRole.values
    ]
    return {"type": RESP, "roles": roles, "notes": list(notes), **extra}


def changes(*texts, **extra):
    rows = [{"text": t} if isinstance(t, str) else t for t in texts]
    return {"type": CHANGES, "rows": rows, **extra}


def attach(*items, **extra):
    return {"type": ATTACH, "items": [{"caption": c, "document_id": d} for c, d in items], **extra}


def png_bytes(size=(20, 20), mode="RGBA", color=(255, 0, 0, 255)):
    buffer = io.BytesIO()
    Image.new(mode, size, color).save(buffer, "PNG")
    return buffer.getvalue()


def jpeg_bytes(size=(20, 20)):
    buffer = io.BytesIO()
    Image.new("RGB", size, (0, 128, 255)).save(buffer, "JPEG")
    return buffer.getvalue()


def upload(name="doc.pdf", data=b"%PDF-1.4 hello"):
    return SimpleUploadedFile(name, data)


@override_settings(CACHES=LOCMEM_CACHE, RATELIMIT_ENABLE=False)
class DesignerTestCase(TestCase):
    """Shared setup: an author, an employer (cannot author), a draft document,
    and an isolated MEDIA_ROOT so file tests never touch real storage."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media = tempfile.mkdtemp(prefix="veye-test-media-")
        cls._override = override_settings(MEDIA_ROOT=cls._media)
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        shutil.rmtree(cls._media, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=False)
        self.author = make_user("6000000001", AccessRoll.GUILD, AccessLevel.LEVEL_3)
        self.employer = make_user("6000000002", AccessRoll.EMPLOYER, AccessLevel.LEVEL_1)
        self.doc = new_doc(self.author, "سند طراحی", DocumentGroup.PROCEDURE)
        self.client.force_authenticate(self.author)

    # -- helpers --

    def url(self, name, doc=None, **kwargs):
        return reverse(f"document-{name}", kwargs={"pk": (doc or self.doc).pk, **kwargs})

    def get_content(self, doc=None):
        response = self.client.get(self.url("content", doc))
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def put(self, sections, doc=None, version="current", **extra):
        doc = doc or self.doc
        if version == "current":
            doc.refresh_from_db()
            version = doc.content_version
        payload = {"base_version": version, "footnote1": "", "footnote2": "", "sections": sections, **extra}
        return self.client.put(self.url("content", doc), payload, format="json")

    def save(self, sections, doc=None, **extra):
        response = self.put(sections, doc, **extra)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def upload_file(self, name="doc.pdf", data=b"%PDF-1.4 hello", doc=None):
        return self.client.post(
            self.url("upload-file", doc), {"file": upload(name, data)}, format="multipart"
        )


class ContentRoundTripTests(DesignerTestCase):
    def test_a_new_document_has_an_empty_body(self):
        data = self.get_content()
        self.assertEqual(data["version"], 0)
        self.assertTrue(data["editable"])
        self.assertEqual(data["sections"], [])
        self.assertIsNone(data["logo_url"])
        self.assertEqual(data["previous_changes"], [])
        self.assertEqual(data["document"]["full_code"], "PR-01-01")

    def test_every_block_type_round_trips(self):
        other = new_doc(self.author, "مستند مرجع", DocumentGroup.FORM)
        saved = self.save(
            [
                short("1-هدف", "", "متن سوم"),
                long_block("2-توضیحات", "متن **مهم** و ~~مایل~~ و --زیرخط--", ["کادر اضافه"]),
                resp(
                    {ResponsibilityRole.CASH_ACCOUNT: {"post": "مدیر مالی", "supervisor": "ناظر مالی", "text": "شرح"}},
                    notes=["توضیح ۱", "توضیح ۲"],
                ),
                changes("اصلاح بند ۳"),
                attach(("فرم درخواست", other.pk)),
            ],
            footnote1="واحد برنامه ریزی",
            footnote2="با احترام",
        )

        self.assertEqual(saved["version"], 1)
        self.assertEqual(saved["footnote1"], "واحد برنامه ریزی")
        self.assertEqual(saved["footnote2"], "با احترام")
        types = [s["type"] for s in saved["sections"]]
        self.assertEqual(types, [SHORT, LONG, RESP, CHANGES, ATTACH])

        self.assertEqual(saved["sections"][0]["lines"], ["1-هدف", "", "متن سوم"], "blank lines are kept")
        self.assertEqual(saved["sections"][1]["extra_boxes"], ["کادر اضافه"])

        roles = {r["role"]: r for r in saved["sections"][2]["roles"]}
        self.assertEqual(roles["cash_account"]["post"], "مدیر مالی")
        self.assertEqual(saved["sections"][2]["notes"], ["توضیح ۱", "توضیح ۲"])
        self.assertEqual([r["role"] for r in saved["sections"][2]["roles"]], list(ResponsibilityRole.values))

        self.assertEqual(saved["sections"][3]["rows"][0]["text"], "اصلاح بند ۳")
        item = saved["sections"][4]["items"][0]
        self.assertEqual(item["caption"], "فرم درخواست")
        self.assertEqual(item["document"]["full_code"], "FR-01-01")

        # And a fresh GET returns exactly what the save returned.
        self.assertEqual(self.get_content()["sections"], saved["sections"])

    def test_rich_text_and_whitespace_are_stored_verbatim(self):
        """The PDF renderer parses **bold**, ~~italic~~ and --underline-- itself
        (to_make_pdf.py:458-541), so the markers must reach it untouched, along
        with the author's own line breaks and spacing."""
        body = "  **پررنگ** ~~مایل~~ --زیرخط--\n\nخط دوم   با فاصله\n"
        saved = self.save([long_block("۲-توضیحات", body)])
        self.assertEqual(saved["sections"][0]["body"], body)

    def test_saving_marks_the_content_saved_and_advances_the_row_action(self):
        self.assertEqual(self.doc.action, "complete")
        self.save([short("الف")])
        self.doc.refresh_from_db()
        self.assertIsNotNone(self.doc.content_saved_at)
        self.assertEqual(self.doc.content_version, 1)
        self.assertEqual(self.doc.action, "finish")

    def test_reordering_keeps_section_identity(self):
        first = self.save([short("الف"), short("ب"), short("ج")])
        ids = [s["id"] for s in first["sections"]]

        reordered = [
            {**first["sections"][2]},
            {**first["sections"][0]},
            {**first["sections"][1]},
        ]
        second = self.save(reordered)
        self.assertEqual([s["id"] for s in second["sections"]], [ids[2], ids[0], ids[1]])
        self.assertEqual([s["lines"][0] for s in second["sections"]], ["ج", "الف", "ب"])
        self.assertEqual(Section.objects.filter(document=self.doc).count(), 3, "no sections were duplicated")

    def test_sections_left_out_of_a_save_are_deleted_with_their_children(self):
        first = self.save([short("الف"), resp(notes=["x"]), changes("تغییر")])
        self.assertTrue(ResponsibilityRow.objects.exists())
        self.assertTrue(ChangeTableRow.objects.exists())

        self.save([first["sections"][0]])
        self.assertEqual(Section.objects.filter(document=self.doc).count(), 1)
        self.assertFalse(ResponsibilityRow.objects.exists())
        self.assertFalse(ChangeTableRow.objects.exists())

    def test_an_unknown_section_id_is_treated_as_new(self):
        saved = self.save([short("الف", id=999999)])
        self.assertEqual(len(saved["sections"]), 1)
        self.assertNotEqual(saved["sections"][0]["id"], 999999)

    def test_a_section_id_of_the_wrong_type_is_not_reused(self):
        first = self.save([short("الف")])
        saved = self.save([long_block("ع", "ب", id=first["sections"][0]["id"])])
        self.assertEqual(saved["sections"][0]["type"], LONG)
        self.assertNotEqual(saved["sections"][0]["id"], first["sections"][0]["id"])

    def test_the_designer_takes_no_hardcoded_demo_rows(self):
        """V_1.0 pre-filled every new Changes Table with two demo rows
        («Changed Upcoming to Previous», dated 1403/07/27 — utils.py:1243-1247)."""
        saved = self.save([changes()])
        self.assertEqual(saved["sections"][0]["rows"], [])
        self.assertFalse(ChangeTableRow.objects.exists())


class ValidationTests(DesignerTestCase):
    def assertRejected(self, sections, *fragments, **kwargs):
        response = self.put(sections, **kwargs)
        self.assertEqual(response.status_code, 400, response.data)
        text = " ".join(str(m) for m in response.data.get("sections", []))
        for fragment in fragments:
            self.assertIn(fragment, text)
        return response

    def test_errors_name_the_section_and_field(self):
        self.assertRejected(
            [short("ok"), long_block("ع" * 501)],
            "بخش 2 (تشریحی بلند)",
            "عنوان",
        )

    def test_unknown_block_type(self):
        self.assertRejected([{"type": "Nonsense"}], "بخش 1", "نامعتبر")

    def test_responsibilities_need_all_four_distinct_roles(self):
        block = resp()
        block["roles"] = block["roles"][:3]
        self.assertRejected([block], "بخش 1")

        block = resp()
        block["roles"][3] = {**block["roles"][0]}  # responder twice, supervisor missing
        self.assertRejected([block], "هر چهار ردیف")

    def test_only_one_responsibilities_and_one_changes_block(self):
        self.assertRejected([resp(), resp()], "فقط یک بخش")
        self.assertRejected([changes(), changes()], "فقط یک بخش")

    def test_a_blank_change_row_is_rejected(self):
        self.assertRejected([changes("  ")], "عنوان تغییر را وارد کنید")

    def test_an_attachment_needs_a_caption_and_a_target(self):
        other = new_doc(self.author, "هدف", DocumentGroup.FORM)
        self.assertRejected([attach(("", other.pk))], "عنوان ضمیمه را بنویسید")
        self.assertRejected(
            [{"type": ATTACH, "items": [{"caption": "بدون هدف"}]}], "مستند ضمیمه را انتخاب کنید"
        )

    def test_duplicate_section_ids_are_rejected(self):
        first = self.save([short("الف")])
        sid = first["sections"][0]["id"]
        self.assertRejected([short("الف", id=sid), short("ب", id=sid)], "تکراری")

    def test_too_many_sections(self):
        response = self.put([short("x")] * 101)
        self.assertEqual(response.status_code, 400)

    def test_a_null_byte_is_a_400_not_a_database_error(self):
        # Postgres rejects NUL in text; it must never reach the database.
        self.assertRejected([short("abc\x00def")], "بخش 1")

    def test_a_missing_version_is_rejected(self):
        response = self.client.put(self.url("content"), {"sections": []}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("base_version", response.data)


class ConcurrencyAndLockingTests(DesignerTestCase):
    def test_a_stale_version_is_a_conflict(self):
        self.save([short("الف")])  # version is now 1
        response = self.put([short("ب")], version=0)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "version_conflict")
        self.assertEqual(response.data["current_version"], 1)
        self.assertEqual(self.get_content()["sections"][0]["lines"], ["الف"], "the losing save changed nothing")

    def test_a_document_past_draft_is_locked(self):
        self.save([short("الف")])
        for status in (
            DocumentStatus.AWAITING_CONFIRMATION,
            DocumentStatus.AWAITING_APPROVAL,
            DocumentStatus.UNDER_CONTROL,
            DocumentStatus.OBSOLETE,
        ):
            finalize(self.doc, status)
            response = self.put([short("تغییر")])
            self.assertEqual(response.status_code, 409, status)
            self.assertEqual(response.data["code"], "content_locked", status)
            self.assertEqual(self.upload_file().status_code, 409, status)
            data = self.get_content()
            self.assertFalse(data["editable"], status)
            self.assertEqual(data["sections"][0]["lines"], ["الف"], "still readable")

    def test_permissions(self):
        self.client.force_authenticate(self.employer)
        self.assertEqual(self.client.get(self.url("content")).status_code, 200)
        self.assertEqual(self.put([short("x")]).status_code, 403)
        self.assertEqual(self.upload_file().status_code, 403)

        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url("content")).status_code, 401)
        self.assertEqual(self.put([short("x")]).status_code, 401)

    def test_unknown_document(self):
        response = self.client.get(reverse("document-content", kwargs={"pk": 999999}))
        self.assertEqual(response.status_code, 404)


class ChangeTableTests(DesignerTestCase):
    def test_new_rows_get_the_servers_date_and_ignore_the_clients(self):
        saved = self.save([changes({"text": "الف", "date": "1999-01-01"})])
        row = saved["sections"][0]["rows"][0]
        self.assertEqual(row["date"], timezone.localdate())
        self.assertNotEqual(row["date"], date(1999, 1, 1))

    def test_an_existing_row_keeps_its_identity_and_date(self):
        first = self.save([changes("الف")])
        row = ChangeTableRow.objects.get()
        ChangeTableRow.objects.filter(pk=row.pk).update(date=date(2020, 3, 4))

        second = self.save(
            [{**first["sections"][0], "rows": [{"id": row.pk, "text": "الف ویرایش‌شده"}, {"text": "ب"}]}]
        )
        rows = second["sections"][0]["rows"]
        self.assertEqual(rows[0]["id"], row.pk)
        self.assertEqual(rows[0]["text"], "الف ویرایش‌شده")
        self.assertEqual(rows[0]["date"], date(2020, 3, 4), "the log's date can't be rewritten by a save")
        self.assertEqual(rows[1]["date"], timezone.localdate())

    def test_a_row_id_from_elsewhere_is_treated_as_new(self):
        other = new_doc(self.author, "سند دیگر", DocumentGroup.FORM)
        self.save([changes("مال دیگری")], doc=other)
        foreign = ChangeTableRow.objects.get()
        ChangeTableRow.objects.filter(pk=foreign.pk).update(date=date(2001, 1, 1))

        saved = self.save([changes({"id": foreign.pk, "text": "دزدی"})])
        self.assertNotEqual(saved["sections"][0]["rows"][0]["id"], foreign.pk)
        foreign.refresh_from_db()
        self.assertEqual(foreign.text, "مال دیگری")

    def test_earlier_revisions_appear_as_frozen_history(self):
        self.save([changes("ویرایش اول")])
        ChangeTableRow.objects.update(date=date(2024, 1, 1))
        finalize(self.doc)
        rev2 = services.create_revision(user=self.author, document_id=self.doc.pk)
        self.assertEqual(rev2.revision, 2)

        # The copy-forward starts the new revision's table empty...
        data = self.get_content(rev2)
        self.assertEqual(data["sections"][0]["rows"], [])
        # ...while the earlier row shows up as history, tagged with its edition.
        history = data["previous_changes"]
        self.assertEqual([h["text"] for h in history], ["ویرایش اول"])
        self.assertEqual((history[0]["revision"], history[0]["revision_display"]), (1, "01"))

        self.save([changes("ویرایش دوم")], doc=rev2)
        finalize(rev2)
        rev3 = services.create_revision(user=self.author, document_id=rev2.pk)
        history = self.get_content(rev3)["previous_changes"]
        self.assertEqual([(h["revision_display"], h["text"]) for h in history], [("01", "ویرایش اول"), ("02", "ویرایش دوم")])

    def test_history_reaches_back_further_than_one_revision(self):
        """V_1.0 fetched only the immediately previous revision's JSON
        (deliver_convert.py:163-197), so revision 3's table lost revision 1."""
        doc = self.doc
        for edition in range(1, 5):
            self.save([changes(f"تغییر {edition}")], doc=doc)
            finalize(doc)
            doc = services.create_revision(user=self.author, document_id=doc.pk)
        texts = [h["text"] for h in self.get_content(doc)["previous_changes"]]
        self.assertEqual(texts, ["تغییر 1", "تغییر 2", "تغییر 3", "تغییر 4"])

    def test_history_does_not_leak_between_documents(self):
        other = new_doc(self.author, "سند دیگر", DocumentGroup.FORM)
        self.save([changes("مال دیگری")], doc=other)
        finalize(other)
        services.create_revision(user=self.author, document_id=other.pk)
        self.assertEqual(self.get_content()["previous_changes"], [])


class AttachmentTests(DesignerTestCase):
    def test_a_document_cannot_attach_itself(self):
        response = self.put([attach(("خودم", self.doc.pk))])
        self.assertEqual(response.status_code, 400)
        self.assertIn("خودش", " ".join(response.data["sections"]))

    def test_an_unknown_target_is_rejected(self):
        response = self.put([attach(("ناموجود", 999999))])
        self.assertEqual(response.status_code, 400)

    def test_attachments_can_be_added_and_removed(self):
        a = new_doc(self.author, "الف", DocumentGroup.FORM)
        b = new_doc(self.author, "ب", DocumentGroup.FORM)
        first = self.save([attach(("اولی", a.pk), ("دومی", b.pk))])
        self.assertEqual([i["document"]["id"] for i in first["sections"][0]["items"]], [a.pk, b.pk])

        second = self.save([attach(("دومی", b.pk))])
        self.assertEqual(len(second["sections"][0]["items"]), 1)
        self.assertEqual(AttachmentReference.objects.count(), 1, "V_1.0 could never remove a linked row")

    def test_a_referenced_document_cannot_be_deleted(self):
        target = new_doc(self.author, "هدف", DocumentGroup.FORM)
        self.save([attach(("ضمیمه", target.pk))])
        with self.assertRaises(ProtectedError):
            target.delete()

    def test_the_payload_reports_the_targets_live_status(self):
        target = new_doc(self.author, "هدف", DocumentGroup.FORM)
        self.save([attach(("ضمیمه", target.pk))])
        finalize(target, DocumentStatus.OBSOLETE)
        item = self.get_content()["sections"][0]["items"][0]
        self.assertEqual(item["document"]["status"], "OBSOLETE")
        self.assertEqual(item["document"]["status_label"], "منسوخ شده")


class FileTests(DesignerTestCase):
    def test_upload_and_authenticated_download(self):
        response = self.upload_file("گزارش.pdf", b"%PDF-1.4 content")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["name"], "گزارش.pdf")
        self.assertEqual(response.data["kind"], "DOCUMENT")
        self.assertEqual(response.data["size"], len(b"%PDF-1.4 content"))

        download = self.client.get(self.url("download-file", file_id=response.data["id"]))
        self.assertEqual(download.status_code, 200)
        self.assertEqual(b"".join(download.streaming_content), b"%PDF-1.4 content")
        self.assertIn("attachment", download["Content-Disposition"])
        self.assertIn("filename*=utf-8''", download["Content-Disposition"], "Persian names survive")

        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url("download-file", file_id=response.data["id"])).status_code, 401)

    def test_kind_comes_from_the_extension_not_the_client(self):
        for name, kind in (("a.png", "PICTURE"), ("a.pdf", "DOCUMENT"), ("a.mp4", "VIDEO"), ("a.XLSX", "DOCUMENT")):
            response = self.upload_file(name, b"data-" + name.encode())
            self.assertEqual(response.status_code, 201, (name, response.data))
            self.assertEqual(response.data["kind"], kind, name)

    def test_disallowed_empty_and_oversized_files(self):
        self.assertEqual(self.upload_file("virus.exe", b"MZ").status_code, 400)
        self.assertEqual(self.upload_file("noextension", b"data").status_code, 400)
        self.assertEqual(self.upload_file("empty.pdf", b"").status_code, 400)
        with override_settings(DOCUMENT_FILE_MAX_BYTES=10):
            response = self.upload_file("big.pdf", b"x" * 11)
            self.assertEqual(response.status_code, 400)
            self.assertIn("مگابایت", str(response.data))
        self.assertEqual(DocumentFile.objects.count(), 0)

    def test_the_same_bytes_are_stored_once_per_document(self):
        first = self.upload_file("a.pdf", b"identical")
        with self.captureOnCommitCallbacks(execute=True):
            again = self.upload_file("renamed.pdf", b"identical")
        self.assertEqual((first.status_code, again.status_code), (201, 200))
        self.assertEqual(first.data["id"], again.data["id"])
        self.assertEqual(DocumentFile.objects.count(), 1)
        # A duplicate must not leave a second copy of the bytes behind.
        stored = os.listdir(os.path.join(self._media, "document_files", str(self.doc.pk)))
        self.assertEqual(len(stored), 1, stored)

    def test_same_name_different_content_never_collides(self):
        """V_1.0 kept one shared bucket keyed by bare filename and reused any
        existing object with the same name (utils.py:1690-1732): two documents
        attaching *different* files both called form.docx got the same one."""
        one = self.upload_file("form.docx", b"version one")
        two = self.upload_file("form.docx", b"version two")
        self.assertNotEqual(one.data["id"], two.data["id"])
        contents = {
            b"".join(self.client.get(self.url("download-file", file_id=r.data["id"])).streaming_content)
            for r in (one, two)
        }
        self.assertEqual(contents, {b"version one", b"version two"})

    def test_files_belong_to_one_document(self):
        other = new_doc(self.author, "دیگری", DocumentGroup.FORM)
        mine = self.upload_file("a.pdf", b"shared bytes")
        theirs = self.upload_file("a.pdf", b"shared bytes", doc=other)
        self.assertEqual(theirs.status_code, 201, "the same bytes in another document are a separate file")
        self.assertNotEqual(mine.data["id"], theirs.data["id"])
        # ...and one document's file id doesn't resolve through another document.
        response = self.client.get(self.url("download-file", other, file_id=mine.data["id"]))
        self.assertEqual(response.status_code, 404)

    def test_a_hostile_filename_never_reaches_the_filesystem_path(self):
        response = self.upload_file("../../etc/passwd.txt", b"nope")
        self.assertEqual(response.status_code, 201, response.data)
        record = DocumentFile.objects.get()
        self.assertTrue(record.file.name.startswith(f"document_files/{self.doc.pk}/"), record.file.name)
        self.assertNotIn("..", record.file.name)
        self.assertTrue(os.path.exists(record.file.path))
        self.assertTrue(os.path.realpath(record.file.path).startswith(os.path.realpath(self._media)))

    def test_files_attach_to_a_long_block_through_file_ids(self):
        fid = self.upload_file("a.pdf", b"attached").data["id"]
        saved = self.save([long_block("ع", "ب", file_ids=[fid])])
        files = saved["sections"][0]["files"]
        self.assertEqual([f["id"] for f in files], [fid])
        self.assertEqual(files[0]["name"], "a.pdf")

    def test_a_file_from_another_document_cannot_be_attached(self):
        other = new_doc(self.author, "دیگری", DocumentGroup.FORM)
        foreign = self.upload_file("a.pdf", b"theirs", doc=other).data["id"]
        response = self.put([long_block("ع", "ب", file_ids=[foreign])])
        self.assertEqual(response.status_code, 400)
        self.assertIn("متعلق به این مستند نیست", " ".join(response.data["sections"]))

    def test_files_no_longer_referenced_are_deleted_on_save(self):
        kept = self.upload_file("keep.pdf", b"keep").data["id"]
        dropped = self.upload_file("drop.pdf", b"drop").data["id"]
        abandoned = self.upload_file("abandoned.pdf", b"abandoned").data["id"]
        paths = {f.id: f.file.path for f in DocumentFile.objects.all()}
        self.assertEqual(set(paths), {kept, dropped, abandoned})
        self.assertTrue(all(os.path.exists(p) for p in paths.values()))

        with self.captureOnCommitCallbacks(execute=True):
            self.save([long_block("ع", "ب", file_ids=[kept, dropped])])
        self.assertEqual(
            set(DocumentFile.objects.values_list("id", flat=True)),
            {kept, dropped},
            "an upload no save ever referenced is cleaned up",
        )
        self.assertFalse(os.path.exists(paths[abandoned]), "its stored bytes are removed too")

        with self.captureOnCommitCallbacks(execute=True):
            self.save([long_block("ع", "ب", file_ids=[kept])])
        self.assertEqual(list(DocumentFile.objects.values_list("id", flat=True)), [kept])
        self.assertFalse(os.path.exists(paths[dropped]), "a file removed from its block is deleted")
        self.assertTrue(os.path.exists(paths[kept]))

    def test_removing_a_block_removes_its_files(self):
        fid = self.upload_file("a.pdf", b"gone soon").data["id"]
        self.save([long_block("ع", "ب", file_ids=[fid])])
        path = DocumentFile.objects.get().file.path
        with self.captureOnCommitCallbacks(execute=True):
            self.save([])
        self.assertFalse(DocumentFile.objects.exists())
        self.assertFalse(os.path.exists(path))

    def test_upload_requires_a_file(self):
        response = self.client.post(self.url("upload-file"), {}, format="multipart")
        self.assertEqual(response.status_code, 400)


class LogoTests(DesignerTestCase):
    def post_logo(self, name, data, doc=None):
        return self.client.post(self.url("logo", doc), {"logo": upload(name, data)}, format="multipart")

    def test_a_png_is_stored_and_served(self):
        response = self.post_logo("logo.png", png_bytes())
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("/api/v1/documents/", response.data["logo_url"])

        self.doc.refresh_from_db()
        self.assertTrue(self.doc.logo.name.endswith(".png"))
        self.assertTrue(self.doc.logo.name.startswith(f"logos/{self.doc.pk}/"))

        served = self.client.get(self.url("logo"))
        self.assertEqual(served.status_code, 200)
        self.assertEqual(served["Content-Type"], "image/png")
        self.assertEqual(Image.open(io.BytesIO(b"".join(served.streaming_content))).format, "PNG")

    def test_a_jpeg_is_converted_to_png(self):
        """The PDF renderer paints a black box for any logo whose path lacks
        '.png' (to_make_pdf.py:159-160), so a .jpg logo silently became a
        black square in V_1.0."""
        self.post_logo("photo.jpg", jpeg_bytes())
        self.doc.refresh_from_db()
        with self.doc.logo.open("rb") as handle:
            self.assertEqual(Image.open(handle).format, "PNG")
        self.assertTrue(self.doc.logo.name.endswith(".png"))

    def test_a_large_logo_is_downscaled(self):
        self.post_logo("big.png", png_bytes(size=(3000, 2000)))
        self.doc.refresh_from_db()
        with self.doc.logo.open("rb") as handle:
            width, height = Image.open(handle).size
        self.assertLessEqual(max(width, height), 1024)
        self.assertAlmostEqual(width / height, 1.5, places=1, msg="aspect ratio preserved")

    def test_transparency_survives(self):
        self.post_logo("t.png", png_bytes(color=(0, 0, 0, 0)))
        self.doc.refresh_from_db()
        with self.doc.logo.open("rb") as handle:
            self.assertEqual(Image.open(handle).mode, "RGBA")

    def test_something_that_is_not_an_image_is_rejected(self):
        response = self.post_logo("logo.png", b"<html>not an image</html>")
        self.assertEqual(response.status_code, 400)
        self.assertIn("تصویر معتبری نیست", str(response.data))
        self.doc.refresh_from_db()
        self.assertFalse(self.doc.logo)

    def test_an_oversized_logo_is_rejected(self):
        with override_settings(LOGO_MAX_BYTES=100):
            response = self.post_logo("big.png", png_bytes(size=(200, 200)))
        self.assertEqual(response.status_code, 400)
        self.assertIn("مگابایت", str(response.data))

    def test_replacing_and_removing_delete_the_stored_file(self):
        self.post_logo("one.png", png_bytes())
        self.doc.refresh_from_db()
        first = self.doc.logo.path
        with self.captureOnCommitCallbacks(execute=True):
            self.post_logo("two.png", png_bytes(color=(0, 255, 0, 255)))
        self.assertFalse(os.path.exists(first), "the replaced logo is removed from disk")

        self.doc.refresh_from_db()
        second = self.doc.logo.path
        self.assertTrue(os.path.exists(second))
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(self.url("logo"))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["logo_url"])
        self.assertFalse(os.path.exists(second))
        self.assertEqual(self.client.get(self.url("logo")).status_code, 404)

    def test_logo_needs_authentication_and_a_draft(self):
        self.post_logo("l.png", png_bytes())
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url("logo")).status_code, 401)

        self.client.force_authenticate(self.author)
        finalize(self.doc)
        self.assertEqual(self.post_logo("l2.png", png_bytes()).status_code, 409)
        self.assertEqual(self.client.delete(self.url("logo")).status_code, 409)
        self.assertEqual(self.client.get(self.url("logo")).status_code, 200, "reading stays open")


class RegisterColumnTests(DesignerTestCase):
    def columns(self, doc=None):
        doc = doc or self.doc
        row = next(
            r for r in self.client.get(reverse("document-list")).data["results"] if r["id"] == doc.pk
        )
        return row["responsibilities"]

    def test_columns_follow_the_row_labels_not_the_position(self):
        """V_1.0 filled حسابکش / پاسخ خواه / پاسخگو from rows 1 / 2 / 3, i.e. the
        row labeled 'Responder' landed under حسابکش and 'Cash Account' under
        پاسخگو. The product owner confirmed that was a swap."""
        self.save(
            [
                resp(
                    {
                        ResponsibilityRole.RESPONDER: {"post": "پست-پاسخگو", "supervisor": "ن۱"},
                        ResponsibilityRole.RECEIVER: {"post": "پست-دریافت", "supervisor": "ن۲"},
                        ResponsibilityRole.CASH_ACCOUNT: {"post": "پست-حسابکش", "supervisor": "ن۳"},
                        ResponsibilityRole.SUPERVISOR: {"post": "پست-ناظر", "supervisor": "ن۴"},
                    }
                )
            ]
        )
        columns = self.columns()
        self.assertEqual(columns["accountant"], {"post": "پست-حسابکش", "supervisor": "ن۳"})
        self.assertEqual(columns["questioner"], {"post": "پست-دریافت", "supervisor": "ن۲"})
        self.assertEqual(columns["responder"], {"post": "پست-پاسخگو", "supervisor": "ن۱"})
        self.assertEqual(set(columns), {"accountant", "questioner", "responder"}, "the 4th row has no column")

    def test_an_empty_row_is_none_not_a_blank_pair(self):
        self.save([resp({ResponsibilityRole.RESPONDER: {"post": "فقط سمت"}})])
        columns = self.columns()
        self.assertEqual(columns["responder"], {"post": "فقط سمت", "supervisor": ""})
        self.assertIsNone(columns["accountant"])
        self.assertIsNone(columns["questioner"])

    def test_a_row_with_only_a_description_does_not_fill_the_column(self):
        self.save([resp({ResponsibilityRole.RESPONDER: {"text": "شرح بدون سمت"}})])
        self.assertIsNone(self.columns()["responder"])

    def test_a_document_without_the_block_has_no_columns(self):
        self.save([short("الف")])
        self.assertEqual(self.columns(), {"accountant": None, "questioner": None, "responder": None})

    def test_the_register_does_not_query_per_row(self):
        for i in range(8):
            doc = new_doc(self.author, f"سند {i}", DocumentGroup.FORM)
            self.save([resp({ResponsibilityRole.RESPONDER: {"post": f"پست {i}"}})], doc=doc)
        # count + page + sign-offs + responsibility sections + their rows
        with self.assertNumQueries(5):
            rows = self.client.get(reverse("document-list")).data["results"]
        self.assertEqual(sum(1 for r in rows if r["responsibilities"]["responder"]), 8)

    def test_can_edit_flag(self):
        finished = finalize(new_doc(self.author, "تمام‌شده", DocumentGroup.FORM))
        rows = {r["id"]: r for r in self.client.get(reverse("document-list")).data["results"]}
        self.assertTrue(rows[self.doc.pk]["can_edit"])
        self.assertFalse(rows[finished.pk]["can_edit"])


class CopyForwardTests(DesignerTestCase):
    def build_finished_document(self):
        target = new_doc(self.author, "مرجع", DocumentGroup.FORM)
        self.client.post(
            self.url("logo"), {"logo": upload("l.png", png_bytes())}, format="multipart"
        )
        fid = self.upload_file("attach.pdf", b"attachment bytes").data["id"]
        self.save(
            [
                short("۱-هدف", "متن"),
                long_block("۲-توضیحات", "**متن**", ["کادر"], [fid]),
                resp({ResponsibilityRole.RESPONDER: {"post": "مدیر", "supervisor": "ناظر"}}, notes=["یادداشت"]),
                changes("ویرایش اول"),
                attach(("ضمیمه", target.pk)),
            ],
            footnote1="پاورقی یک",
            footnote2="پاورقی دو",
        )
        finalize(self.doc)
        return target

    def test_a_new_revision_starts_as_a_copy_of_the_previous_one(self):
        target = self.build_finished_document()
        old = self.get_content()

        rev2 = services.create_revision(user=self.author, document_id=self.doc.pk)
        new = self.get_content(rev2)

        self.assertEqual(new["footnote1"], "پاورقی یک")
        self.assertEqual(new["footnote2"], "پاورقی دو")
        self.assertEqual([s["type"] for s in new["sections"]], [s["type"] for s in old["sections"]])
        self.assertEqual(new["sections"][0]["lines"], ["۱-هدف", "متن"])
        self.assertEqual(new["sections"][1]["body"], "**متن**")
        self.assertEqual(new["sections"][1]["extra_boxes"], ["کادر"])
        self.assertEqual(new["sections"][2]["roles"], old["sections"][2]["roles"])
        self.assertEqual(new["sections"][2]["notes"], ["یادداشت"])
        self.assertEqual(new["sections"][4]["items"][0]["document"]["id"], target.pk)
        self.assertIsNotNone(new["logo_url"])

    def test_the_new_revision_is_a_fresh_draft(self):
        self.build_finished_document()
        rev2 = services.create_revision(user=self.author, document_id=self.doc.pk)
        rev2.refresh_from_db()
        self.assertEqual(rev2.status, DocumentStatus.DRAFT)
        self.assertEqual(rev2.content_version, 0)
        self.assertIsNone(rev2.content_saved_at)
        self.assertEqual(rev2.action, "complete", "the author still has to open and save it")

    def test_change_rows_are_not_copied_because_history_already_shows_them(self):
        self.build_finished_document()
        rev2 = services.create_revision(user=self.author, document_id=self.doc.pk)
        data = self.get_content(rev2)
        self.assertEqual(data["sections"][3]["rows"], [], "the new edition's table starts empty")
        self.assertEqual([h["text"] for h in data["previous_changes"]], ["ویرایش اول"])
        self.assertEqual(ChangeTableRow.objects.count(), 1, "one row exists, not two")

    def test_files_and_logo_are_physically_copied(self):
        self.build_finished_document()
        rev2 = services.create_revision(user=self.author, document_id=self.doc.pk)
        old_file, new_file = DocumentFile.objects.get(document=self.doc), DocumentFile.objects.get(document=rev2)

        self.assertNotEqual(old_file.file.name, new_file.file.name)
        with old_file.file.open("rb") as a, new_file.file.open("rb") as b:
            self.assertEqual(a.read(), b.read())
        self.assertEqual((new_file.original_name, new_file.sha256), (old_file.original_name, old_file.sha256))

        self.doc.refresh_from_db()
        rev2.refresh_from_db()
        self.assertNotEqual(self.doc.logo.name, rev2.logo.name)
        with self.doc.logo.open("rb") as a, rev2.logo.open("rb") as b:
            self.assertEqual(a.read(), b.read())

        # Deleting the copy (by saving the new revision without the block) must not
        # reach back into the old revision's file.
        with self.captureOnCommitCallbacks(execute=True):
            self.save([], doc=rev2)
        self.assertFalse(DocumentFile.objects.filter(document=rev2).exists())
        self.assertTrue(os.path.exists(old_file.file.path), "the previous revision's file is untouched")

    def test_the_previous_revision_is_unchanged(self):
        self.build_finished_document()
        before = self.get_content()
        services.create_revision(user=self.author, document_id=self.doc.pk)
        self.assertEqual(self.get_content()["sections"], before["sections"])

    def test_a_revision_of_an_empty_document_copies_nothing(self):
        finalize(self.doc)
        rev2 = services.create_revision(user=self.author, document_id=self.doc.pk)
        self.assertEqual(self.get_content(rev2)["sections"], [])


@skipUnlessDBFeature("has_select_for_update")
class DesignerConcurrencyTests(TransactionTestCase):
    """Two real transactions saving from the same base version: exactly one wins."""

    def setUp(self):
        self.user = make_user("7000000001")
        self.doc = new_doc(self.user, "همزمان", DocumentGroup.POSTER)

    def test_simultaneous_saves_yield_exactly_one_winner(self):
        n, results, barrier = 6, [], threading.Barrier(6)

        def payload(i):
            return {
                "base_version": 0,
                "footnote1": f"f{i}",
                "footnote2": "",
                "sections": [{"type": SHORT, "lines": [f"از رشته {i}"]}],
            }

        def worker(i):
            try:
                barrier.wait()
                content.save_content(user=self.user, document_id=self.doc.pk, data=payload(i))
                results.append("ok")
            except ConflictError as exc:
                results.append(exc.payload["code"])
            except Exception as exc:  # noqa: BLE001
                results.append(repr(exc))
            finally:
                connection.close()

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        [t.start() for t in threads]
        [t.join() for t in threads]

        self.assertEqual(results.count("ok"), 1, results)
        self.assertEqual(results.count("version_conflict"), n - 1, results)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.content_version, 1)
        self.assertEqual(Section.objects.filter(document=self.doc).count(), 1)
