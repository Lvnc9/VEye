"""Company document defaults (Phase 11, ADR-011): set once in «تنظیمات», copied into
every new document when it is created."""
import io
import shutil
import tempfile

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import AccessLevel, AccessRoll
from apps.accounts.tests import LOCMEM_CACHE, make_user
from apps.core.constants import DocumentCategory, DocumentGroup, DocumentStatus
from apps.documents import services as documents
from apps.documents.models import Document

from .models import Company, SetupStep
from .tests import make_company

MEDIA = tempfile.mkdtemp(prefix="veye-defaults-media-")


def tearDownModule():
    shutil.rmtree(MEDIA, ignore_errors=True)


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (8, 8), (200, 0, 0)).save(out, format="PNG")
    return out.getvalue()


@override_settings(MEDIA_ROOT=MEDIA, CACHES=LOCMEM_CACHE)
class DocumentDefaultsTests(TestCase):
    def setUp(self):
        self.root = make_company()
        self.company = Company.objects.get(pk=1)
        self.manager = make_user("5100000001", AccessRoll.EMPLOYER, AccessLevel.LEVEL_1)  # مدیر عامل
        self.author = make_user("5100000002", AccessRoll.GUILD, AccessLevel.LEVEL_3)
        self.client = APIClient()
        self.url = reverse("org-company-document-defaults")

    def create(self, group=DocumentGroup.FORM, title="فرم"):
        return documents.create_document(user=self.author, category=DocumentCategory.INSIDE, title=title, group=group)

    def set_defaults(self, **values):
        Company.objects.filter(pk=1).update(**values)

    # -- the API ---------------------------------------------------------------

    def test_a_manager_sets_the_defaults(self):
        self.client.force_authenticate(self.manager)
        response = self.client.patch(
            self.url,
            {"doc_footnote1": "واحد منابع انسانی", "form_subtitle": "فرم‌های استخدام", "form_show_letter_box": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            response.data["document_defaults"],
            {"doc_footnote1": "واحد منابع انسانی", "doc_footnote2": "", "form_subtitle": "فرم‌های استخدام", "form_show_letter_box": True},
        )
        read = self.client.get(reverse("org-company")).data
        self.assertEqual(read["document_defaults"]["form_subtitle"], "فرم‌های استخدام")

    def test_only_manage_organization_may_change_them(self):
        self.client.force_authenticate(self.author)
        self.assertEqual(self.client.patch(self.url, {"doc_footnote1": "x"}, format="json").status_code, 403)
        # Anyone signed in reads them with the company.
        self.assertIn("document_defaults", self.client.get(reverse("org-company")).data)

    def test_too_long_is_refused_in_persian(self):
        self.client.force_authenticate(self.manager)
        response = self.client.patch(self.url, {"doc_footnote1": "ب" * 256}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_saving_defaults_never_moves_the_setup_bookmark(self):
        self.client.force_authenticate(self.manager)
        self.client.patch(self.url, {"doc_footnote2": "x"}, format="json")
        self.company.refresh_from_db()
        self.assertEqual(self.company.setup_step, SetupStep.DOMAINS)

    # -- applied to new documents ------------------------------------------

    def test_a_new_form_starts_from_the_defaults(self):
        self.set_defaults(doc_footnote1="بالا", doc_footnote2="پایین", form_subtitle="منابع انسانی", form_show_letter_box=True)
        self.company.refresh_from_db()  # logo.save() writes every field back
        self.company.logo.save("logo.png", ContentFile(png()))
        form = self.create()
        self.assertEqual((form.footnote1, form.footnote2), ("بالا", "پایین"))
        self.assertEqual(form.form_settings["header"]["subtitle"], "منابع انسانی")
        self.assertTrue(form.form_settings["header"]["show_letter_box"])
        self.assertTrue(form.logo.name.startswith(f"logos/{form.pk}/"))
        with form.logo.open("rb") as handle:
            self.assertEqual(handle.read(), png())
        # A copy, not the company's file.
        self.assertNotEqual(form.logo.name, self.company.logo.name)

    def test_every_other_document_gets_the_logo_and_footnotes(self):
        self.set_defaults(doc_footnote1="بالا", form_subtitle="فقط فرم")
        procedure = self.create(DocumentGroup.PROCEDURE, "روش")
        self.assertEqual(procedure.footnote1, "بالا")
        self.assertEqual(procedure.form_settings, {})

    def test_later_changes_leave_existing_documents_alone(self):
        self.set_defaults(doc_footnote1="قدیم")
        form = self.create()
        self.set_defaults(doc_footnote1="جدید")
        form.refresh_from_db()
        self.assertEqual(form.footnote1, "قدیم")

    def test_a_revision_copies_its_predecessor_not_the_defaults(self):
        self.set_defaults(doc_footnote1="پیش‌فرض")
        form = self.create()
        Document.objects.filter(pk=form.pk).update(footnote1="ویرایش‌شده", status=DocumentStatus.UNDER_CONTROL)
        self.set_defaults(doc_footnote1="پیش‌فرض تازه")
        revision = documents.create_revision(user=self.manager, document_id=form.pk)  # (a document with no owner node is the مدیر عامل's)
        self.assertEqual(revision.footnote1, "ویرایش‌شده")

    def test_a_missing_logo_file_does_not_stop_creation(self):
        self.company.logo.save("logo.png", ContentFile(png()))
        self.company.logo.storage.delete(self.company.logo.name)
        with self.assertLogs("veye", level="WARNING"):
            form = self.create()
        self.assertFalse(form.logo)

    def test_the_hook_is_registered_once(self):
        from apps.documents.services import NEW_DOCUMENT_HOOKS

        from .document_defaults import apply_to_new_document

        self.assertEqual(NEW_DOCUMENT_HOOKS.count(apply_to_new_document), 1)

    def test_no_company_no_defaults(self):
        Company.objects.all().delete()
        form = self.create()
        self.assertEqual(form.footnote1, "")
        self.assertFalse(form.logo)
