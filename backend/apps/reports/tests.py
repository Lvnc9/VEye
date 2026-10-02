import csv
import io
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AccessLevel, AccessRoll, Capability, User
from apps.core.constants import DocumentCategory, DocumentGroup, DocumentStatus
from apps.documents import services as document_services
from apps.documents import test_support
from apps.documents.models import Document
from apps.projects import services as project_services
from apps.projects.models import Objective

from .csv_export import BOM, safe_cell


def person(code, roll=AccessRoll.GUILD, level=AccessLevel.LEVEL_3, name=None):
    return User.objects.create_user(
        national_code=code, password="pw-for-tests-123", full_name=name or f"کاربر {code}",
        access_roll=roll, access_level=level,
    )


def read_csv(response) -> list[list[str]]:
    body = b"".join(response.streaming_content).decode("utf-8")
    assert body.startswith(BOM), "a UTF-8 BOM first, or Excel reads Persian as mojibake"
    return list(csv.reader(io.StringIO(body[len(BOM):])))


class SafeCellTests(TestCase):
    def test_a_spreadsheet_formula_is_defused(self):
        for text in ("=1+1", "+cmd", "-2+3", "@SUM(A1)", "\tfoo", "\rfoo"):
            self.assertEqual(safe_cell(text), "'" + text, text)

    def test_ordinary_text_and_numbers_are_untouched(self):
        self.assertEqual(safe_cell("روش اجرایی"), "روش اجرایی")
        self.assertEqual(safe_cell(-5), -5)  # a real negative number is not text
        self.assertEqual(safe_cell(0), 0)

    def test_none_is_empty_and_booleans_are_persian(self):
        self.assertEqual(safe_cell(None), "")
        self.assertEqual((safe_cell(True), safe_cell(False)), ("بله", "خیر"))


class CapabilityTests(TestCase):
    def test_who_gets_the_reports_surface(self):
        guild = person("9700000001")
        hq = person("9700000002", AccessRoll.HEADQUARTERS)
        board = person("9700000003", AccessRoll.EMPLOYER, AccessLevel.LEVEL_3)
        self.assertFalse(guild.has_capability(Capability.VIEW_REPORTS))
        self.assertTrue(hq.has_capability(Capability.VIEW_REPORTS))
        self.assertTrue(board.has_capability(Capability.VIEW_REPORTS))

    def test_the_developer_account_never_does(self):
        developer = User(access_roll=AccessRoll.GUILD, access_level=AccessLevel.LEVEL_3, is_developer=True)
        self.assertFalse(developer.has_capability(Capability.VIEW_REPORTS))


class DocumentsExportTests(TestCase):
    def setUp(self):
        self.org = test_support.ensure_org()
        self.author = person("9710000001", name="نویسنده")
        test_support.lead_of(self.author, self.org.rag)
        self.hq = person("9710000002", AccessRoll.HEADQUARTERS)
        self.guild = person("9710000003")
        self.url = reverse("reports-documents-export")

    def doc(self, title, group=DocumentGroup.PROCEDURE):
        return document_services.create_document(
            user=self.author, category=DocumentCategory.INSIDE, title=title, group=group, owner_node=self.org.rag
        )

    def get(self, user, **params):
        client = APIClient()
        client.force_authenticate(user)
        return client.get(self.url, params)

    def test_requires_authentication_and_the_capability(self):
        self.assertEqual(APIClient().get(self.url).status_code, 401)
        self.assertEqual(self.get(self.guild).status_code, 403)
        self.assertEqual(self.get(self.hq).status_code, 200)

    def test_it_is_a_csv_attachment_with_an_ascii_name(self):
        response = self.get(self.hq)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertRegex(response["Content-Disposition"], r'^attachment; filename="documents-\d{8}\.csv"$')
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_one_row_per_revision_with_the_registers_columns(self):
        document = self.doc("روش کنترل")
        rows = read_csv(self.get(self.hq))
        self.assertEqual(rows[0][:3], ["کد مستند", "عنوان", "گروه"])
        self.assertEqual(len(rows), 2)
        row = dict(zip(rows[0], rows[1]))
        self.assertEqual(row["کد مستند"], document.full_code)
        self.assertEqual(row["عنوان"], "روش کنترل")
        self.assertEqual(row["گروه"], "روش اجرایی")
        self.assertEqual(row["وضعیت"], DocumentStatus.DRAFT.label)
        self.assertEqual(row["گرهٔ مالک"], "RAG")
        self.assertEqual(row["ایجادکننده"], "نویسنده")
        self.assertRegex(row["تاریخ ایجاد"], r"^\d{4}/\d{2}/\d{2}$")  # Jalali, like everywhere else

    def test_the_registers_filters_apply(self):
        self.doc("الف", DocumentGroup.PROCEDURE)
        self.doc("ب", DocumentGroup.FORM)
        titles = [r[1] for r in read_csv(self.get(self.hq, group=DocumentGroup.FORM))[1:]]
        self.assertEqual(titles, ["ب"])
        self.assertEqual(len(read_csv(self.get(self.hq, search="الف"))), 2)
        self.assertEqual(len(read_csv(self.get(self.hq, status="nonsense"))), 1)  # header only, never everything

    def test_a_title_that_is_a_formula_cannot_run(self):
        self.doc("=HYPERLINK(\"http://x\")")
        self.assertEqual(read_csv(self.get(self.hq))[1][1], "'=HYPERLINK(\"http://x\")")

    def test_an_empty_register_is_just_the_header(self):
        self.assertEqual(len(read_csv(self.get(self.hq))), 1)


class ProjectsExportTests(TestCase):
    def setUp(self):
        self.org = test_support.ensure_org()
        self.hq = person("9720000001", AccessRoll.HEADQUARTERS)
        self.board = person("9720000002", AccessRoll.EMPLOYER, AccessLevel.LEVEL_3)  # sees every project
        self.member = person("9720000003", name="همکار")
        self.url = reverse("reports-projects-export")
        self.today = timezone.localdate()

    def project(self, name, section=None, actor=None, **kw):
        return project_services.create_project(
            actor=actor or self.board, section=section or self.org.rag, name=name,
            members=[{"user": self.member}], **kw,
        )

    def get(self, user, **params):
        client = APIClient()
        client.force_authenticate(user)
        return client.get(self.url, params)

    def test_requires_the_capability(self):
        self.assertEqual(self.get(self.member).status_code, 403)

    def test_a_row_per_project_with_derived_progress_and_overdue(self):
        project = self.project(
            "پروژه الف",
            objectives=[
                {"title": "یک", "assignees": [self.member], "due_on": self.today + timedelta(days=9), "weight": 1},
                {"title": "دو", "assignees": [self.member], "due_on": self.today + timedelta(days=9), "weight": 3},
            ],
        )
        done, late = project.objectives.order_by("id")
        Objective.objects.filter(pk=done.pk).update(status="DONE")
        Objective.objects.filter(pk=late.pk).update(due_on=self.today - timedelta(days=2))
        rows = read_csv(self.get(self.board))
        row = dict(zip(rows[0], rows[1]))
        self.assertEqual((row["نام پروژه"], row["بخش"], row["وضعیت"]), ("پروژه الف", "RAG", "در حال اجرا"))
        self.assertEqual(row["پیشرفت (٪)"], "25")  # weight 1 done of 4
        self.assertEqual((row["تعداد ریزهدف"], row["ریزهدف دیرکرد"], row["تعداد اعضا"]), ("2", "1", "2"))
        self.assertEqual(row["مدیران پروژه"], self.board.full_name)
        self.assertEqual(row["بایگانی‌شده"], "خیر")

    def test_a_project_with_no_live_objective_has_no_progress_not_zero(self):
        self.project("خالی")
        row = dict(zip(*read_csv(self.get(self.board))[:2]))
        self.assertEqual(row["پیشرفت (٪)"], "")

    def test_only_what_the_person_may_read(self):
        self.project("پروژه الف")
        # hq neither is a member nor leads a section above it: the export is as empty as /projects/
        self.assertEqual(len(read_csv(self.get(self.hq))), 1)
        test_support.lead_of(self.hq, self.org.ai)  # leads the واحد above RAG
        self.assertEqual(len(read_csv(self.get(self.hq))), 2)

    def test_archived_projects_are_a_separate_export(self):
        project = self.project("بایگانی")
        project_services.archive_project(project, actor=self.board)
        self.assertEqual(len(read_csv(self.get(self.board))), 1)
        rows = read_csv(self.get(self.board, archived="1"))
        self.assertEqual((len(rows), dict(zip(*rows[:2]))["بایگانی‌شده"]), (2, "بله"))
