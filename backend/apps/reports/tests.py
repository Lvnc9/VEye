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


# ---------------------------------------------------------------------------
# The KPI numbers
# ---------------------------------------------------------------------------

from datetime import datetime, timezone as dt_timezone  # noqa: E402

from apps.core.constants import DocumentEventKind  # noqa: E402
from apps.documents.models import DocumentEvent  # noqa: E402

from . import kpi  # noqa: E402

S, C, A, R = (DocumentEventKind.SUBMITTED, DocumentEventKind.CONFIRMED, DocumentEventKind.APPROVED, DocumentEventKind.RETURNED)
T0 = datetime(2026, 9, 1, 8, 0, tzinfo=dt_timezone.utc)


def at(days=0, hours=0):
    return T0 + timedelta(days=days, hours=hours)


class PairedStepsTests(TestCase):
    def test_a_clean_run_has_one_confirm_and_one_approve_step(self):
        steps = kpi.paired_steps([(1, S, at(0)), (1, C, at(2)), (1, A, at(5))])
        self.assertEqual(steps["confirm"], [(at(2), timedelta(days=2))])
        self.assertEqual(steps["approve"], [(at(5), timedelta(days=3))])

    def test_a_return_ends_the_attempt_and_the_next_submit_starts_fresh(self):
        steps = kpi.paired_steps(
            [(1, S, at(0)), (1, C, at(1)), (1, R, at(2)), (1, S, at(10)), (1, C, at(11))]
        )
        # The days spent in draft after the return (2 → 10) belong to no step.
        self.assertEqual([d for _, d in steps["confirm"]], [timedelta(days=1), timedelta(days=1)])
        self.assertEqual(steps["approve"], [])

    def test_a_return_after_a_submit_discards_it(self):
        steps = kpi.paired_steps([(1, S, at(0)), (1, R, at(3)), (1, C, at(4))])
        self.assertEqual(steps["confirm"], [])  # a CONFIRMED with no live SUBMITTED pairs with nothing

    def test_documents_never_pair_across_each_other(self):
        steps = kpi.paired_steps([(1, S, at(0)), (2, C, at(1)), (2, A, at(4))])
        self.assertEqual(steps["confirm"], [])
        self.assertEqual(steps["approve"], [(at(4), timedelta(days=3))])

    def test_an_imported_document_missing_its_submit_still_measures_the_approve_step(self):
        steps = kpi.paired_steps([(1, C, at(0)), (1, A, at(2))])
        self.assertEqual((steps["confirm"], len(steps["approve"])), ([], 1))


class SummaryTests(TestCase):
    def test_counts_only_steps_that_ended_in_the_window(self):
        durations = [(at(1), timedelta(days=9)), (at(20), timedelta(days=2)), (at(25), timedelta(days=4))]
        result = kpi.summarize(durations, since=at(10))
        self.assertEqual(result, {"count": 2, "average_days": 3.0, "median_days": 3.0, "longest_days": 4.0})

    def test_nothing_in_the_window_is_none_not_zero(self):
        self.assertEqual(kpi.summarize([], at(0)), {"count": 0, "average_days": None, "median_days": None, "longest_days": None})

    def test_the_median_is_not_the_mean(self):
        durations = [(at(1), timedelta(days=1)), (at(2), timedelta(days=1)), (at(3), timedelta(days=10))]
        result = kpi.summarize(durations, at(0))
        self.assertEqual((result["average_days"], result["median_days"]), (4.0, 1.0))

    def test_return_rate(self):
        self.assertEqual(kpi.return_rate(6, 3, 1)["rate"], 10.0)
        self.assertIsNone(kpi.return_rate(0, 0, 0)["rate"])

    def test_clamp_days(self):
        self.assertEqual([kpi.clamp_days(x) for x in (None, "x", "", 3, "500", 9999, "30")], [90, 90, 90, 7, 500, 730, 30])


class KpiApiTests(TestCase):
    def setUp(self):
        self.org = test_support.ensure_org()
        self.author = person("9730000001", name="نویسنده")
        test_support.lead_of(self.author, self.org.rag)
        self.board = person("9730000002", AccessRoll.EMPLOYER, AccessLevel.LEVEL_3)
        self.hq = person("9730000003", AccessRoll.HEADQUARTERS)
        self.member = person("9730000004", name="همکار")
        self.url = reverse("reports-kpi")
        self.today = timezone.localdate()

    def get(self, user, **params):
        client = APIClient()
        client.force_authenticate(user)
        return client.get(self.url, params)

    def event(self, document, kind, when):
        event = DocumentEvent.objects.create(
            document=document, kind=kind, from_status="DRAFT", to_status="DRAFT",
            actor=self.author, actor_name="x", actor_title="",
        )
        DocumentEvent.objects.filter(pk=event.pk).update(created_at=when)

    def doc(self, title):
        return document_services.create_document(
            user=self.author, category=DocumentCategory.INSIDE, title=title, group=DocumentGroup.PROCEDURE,
            owner_node=self.org.rag,
        )

    def test_requires_authentication_and_the_capability(self):
        self.assertEqual(APIClient().get(self.url).status_code, 401)
        self.assertEqual(self.get(self.member).status_code, 403)
        self.assertEqual(self.get(self.hq).status_code, 200)

    def test_an_empty_company_is_all_none_and_zero_never_an_error(self):
        data = self.get(self.board).data
        self.assertEqual(data["days"], 90)
        self.assertIsNone(data["documents"]["confirm_step"]["average_days"])
        self.assertIsNone(data["documents"]["returns"]["rate"])
        self.assertEqual(data["documents"]["waiting_now"]["confirmation"], {"count": 0, "oldest_days": None})
        self.assertIsNone(data["projects"]["progress"])
        self.assertEqual(data["projects"]["workload"], [])

    def test_step_times_and_return_rate_come_from_the_event_trail(self):
        now = timezone.now()
        a, b = self.doc("الف"), self.doc("ب")
        DocumentEvent.objects.all().delete()
        self.event(a, S, now - timedelta(days=10))
        self.event(a, C, now - timedelta(days=8))      # confirm step: 2 days
        self.event(a, A, now - timedelta(days=5))      # approve step: 3 days
        self.event(b, S, now - timedelta(days=6))
        self.event(b, R, now - timedelta(days=4))      # a return
        data = self.get(self.board).data["documents"]
        self.assertEqual((data["confirm_step"]["count"], data["confirm_step"]["average_days"]), (1, 2.0))
        self.assertEqual((data["approve_step"]["count"], data["approve_step"]["average_days"]), (1, 3.0))
        self.assertEqual(data["returns"], {"confirmed": 1, "approved": 1, "returned": 1, "decisions": 3, "rate": 33.3})
        self.assertEqual(data["submitted_in_window"], 2)

    def test_days_narrows_the_window(self):
        now = timezone.now()
        a = self.doc("الف")
        DocumentEvent.objects.all().delete()
        self.event(a, S, now - timedelta(days=60))
        self.event(a, C, now - timedelta(days=58))
        self.assertEqual(self.get(self.board, days=90).data["documents"]["confirm_step"]["count"], 1)
        self.assertEqual(self.get(self.board, days=30).data["documents"]["confirm_step"]["count"], 0)

    def test_waiting_now_counts_documents_by_step_with_the_oldest(self):
        now = timezone.now()
        a, b = self.doc("الف"), self.doc("ب")
        Document.objects.filter(pk=a.pk).update(status=DocumentStatus.AWAITING_CONFIRMATION, updated_at=now - timedelta(days=4))
        Document.objects.filter(pk=b.pk).update(status=DocumentStatus.AWAITING_CONFIRMATION, updated_at=now - timedelta(days=1))
        waiting = self.get(self.board).data["documents"]["waiting_now"]
        self.assertEqual(waiting["confirmation"]["count"], 2)
        self.assertEqual(waiting["confirmation"]["oldest_days"], 4.0)
        self.assertEqual(waiting["approval"], {"count": 0, "oldest_days": None})

    def project(self, name, objectives, **kw):
        return project_services.create_project(
            actor=self.board, section=self.org.rag, name=name, members=[{"user": self.member}],
            objectives=objectives, **kw,
        )

    def obj(self, title, days=9, weight=1):
        return {"title": title, "assignees": [self.member], "due_on": self.today + timedelta(days=days), "weight": weight}

    def test_company_progress_is_weighted_across_unfinished_projects(self):
        first = self.project("الف", [self.obj("یک", weight=1), self.obj("دو", weight=1)])
        second = self.project("ب", [self.obj("سه", weight=6)])
        Objective.objects.filter(pk=first.objectives.first().pk).update(status="DONE")        # 1 of 2
        Objective.objects.filter(pk=second.objectives.first().pk).update(status="DONE")       # 6 of 6
        projects = self.get(self.board).data["projects"]
        # (1 + 6) of (2 + 6): weighted by objective weight, NOT the mean of 50 % and 100 %
        self.assertEqual((projects["weight_done"], projects["weight_total"], projects["progress"]), (7, 8, 88))
        self.assertEqual(projects["unfinished_count"], 2)

    def test_finished_and_archived_projects_do_not_count(self):
        done = self.project("تمام", [self.obj("یک")])
        archived = self.project("بایگانی", [self.obj("دو")])
        live = self.project("زنده", [self.obj("سه")])
        project_services.update_project(done, actor=self.board, changes={"status": "DONE"})
        project_services.archive_project(archived, actor=self.board)
        projects = self.get(self.board).data["projects"]
        self.assertEqual(projects["unfinished_count"], 1)
        self.assertEqual(projects["weight_total"], 1)
        self.assertEqual(projects["by_status"]["DONE"], 1)
        self.assertIsNotNone(live)

    def test_workload_counts_open_and_overdue_per_person_busiest_first(self):
        other = person("9730000005", name="دیگری")
        project = project_services.create_project(
            actor=self.board, section=self.org.rag, name="بار کاری", members=[{"user": self.member}, {"user": other}],
            objectives=[
                {"title": "الف", "assignees": [self.member], "due_on": self.today + timedelta(days=9)},
                {"title": "ب", "assignees": [self.member], "due_on": self.today + timedelta(days=9)},
                {"title": "ج", "assignees": [self.member, other], "due_on": self.today + timedelta(days=9)},
                {"title": "د", "assignees": [other], "due_on": self.today + timedelta(days=9)},
            ],
        )
        by_title = {o.title: o for o in project.objectives.all()}
        Objective.objects.filter(pk=by_title["الف"].pk).update(due_on=self.today - timedelta(days=3))  # overdue
        Objective.objects.filter(pk=by_title["ب"].pk).update(status="DONE")                             # closed: not workload
        rows = self.get(self.board).data["projects"]["workload"]
        self.assertEqual([(r["name"], r["open"], r["overdue"]) for r in rows], [("همکار", 2, 1), ("دیگری", 2, 0)])

    def test_a_person_sees_only_the_projects_they_may_read(self):
        self.project("الف", [self.obj("یک")])
        self.assertEqual(self.get(self.hq).data["projects"]["unfinished_count"], 0)  # not a member, leads nothing
        test_support.lead_of(self.hq, self.org.ai)
        self.assertEqual(self.get(self.hq).data["projects"]["unfinished_count"], 1)
