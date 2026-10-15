from datetime import date, timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AccessLevel, AccessRoll, User
from apps.core.constants import DocumentStatus
from apps.documents import test_support
from apps.documents.models import Document
from apps.leave.models import Holiday, LeaveRequest, LeaveStatus
from apps.organization.models import Delegation
from apps.projects.models import MeetingAttendee, Objective, ObjectiveAssignee, Project, ProjectMeeting, ProjectMember
from apps.quality.models import CorrectiveAction, InternalAudit, NonConformance, RiskItem

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "agenda-tests"}}


def person(code, name=None, roll=AccessRoll.GUILD, level=AccessLevel.LEVEL_2):
    return User.objects.create_user(
        national_code=code, password="pw-for-tests-123", full_name=name or f"کاربر {code}", access_roll=roll,
        access_level=level,
    )


@override_settings(CACHES=LOCMEM, RATELIMIT_ENABLE=False)
class AgendaTests(TestCase):
    """Phase 22 «تقویم»: what is on me in a window, and «مرخصی تیم» for a lead."""

    def setUp(self):
        self.org = test_support.ensure_org()
        self.today = timezone.localdate()
        self.me = person("8700000001", "من")
        test_support.lead_of(self.me, self.org.rag)
        self.worker = person("8700000002", "کارمند")
        test_support.member_of(self.worker, self.org.rag, is_primary=True)
        self.other = person("8700000003", "دیگری")
        test_support.member_of(self.other, self.org.cash, is_primary=True)
        self.day = lambda n: self.today + timedelta(days=n)

        project = Project.objects.create(section=self.org.rag, name="پروژه", name_key="پروژه", created_by=self.me)
        member = ProjectMember.objects.create(project=project, user=self.me)
        objective = Objective.objects.create(project=project, title="ریزهدف من", due_on=self.day(3), position=0)
        ObjectiveAssignee.objects.create(objective=objective, member=member)
        Objective.objects.create(project=project, title="ریزهدف دیگری", due_on=self.day(3), position=1)
        meeting = ProjectMeeting.objects.create(project=project, title="جلسهٔ هفتگی", held_on=self.day(5))
        MeetingAttendee.objects.create(meeting=meeting, member=member)
        nc = NonConformance.objects.create(
            title="خطا", description="—", owner_node=self.org.rag, reported_by=self.other, detected_on=self.today
        )
        CorrectiveAction.objects.create(nc=nc, title="اقدام من", assignee=self.me, due_on=self.day(-1))
        InternalAudit.objects.create(title="ممیزی من", scope_node=self.org.rag, lead_auditor=self.me, planned_on=self.day(7))
        RiskItem.objects.create(
            title="ریسک من", description="—", owner_node=self.org.rag, owner=self.me, likelihood=2, impact=2,
            created_by=self.me, review_on=self.day(9),
        )
        test_support.ensure_org()
        self.doc = Document.objects.create(
            category="INSIDE", title="روش", group="PROCEDURE", number=1, status=DocumentStatus.UNDER_CONTROL,
            owner_node=self.org.rag, created_by=self.me, review_due_on=self.day(11),
        )
        LeaveRequest.objects.create(requester=self.me, starts_on=self.day(13), ends_on=self.day(14))
        LeaveRequest.objects.create(
            requester=self.worker, node=self.org.rag, starts_on=self.day(2), ends_on=self.day(4),
            status=LeaveStatus.APPROVED, decided_at=timezone.now(),
        )
        LeaveRequest.objects.create(requester=self.other, node=self.org.cash, starts_on=self.day(2), ends_on=self.day(4))
        Delegation.objects.create(node=self.org.ai, delegate=self.me, starts_on=self.day(1), ends_on=self.day(6))
        Holiday.objects.create(date=self.day(8), title="تعطیل رسمی")

    def agenda(self, user, team=False, start=-5, end=20):
        client = APIClient()
        client.force_authenticate(user)
        params = {"from": self.day(start).isoformat(), "to": self.day(end).isoformat()}
        if team:
            params["team"] = "1"
        response = client.get(reverse("agenda"), params)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_everything_on_me_and_nothing_else(self):
        body = self.agenda(self.me)
        by_kind = {}
        for item in body["items"]:
            by_kind.setdefault(item["kind"], []).append(item["title"])
        self.assertEqual(by_kind["objective"], ["ریزهدف من"])
        self.assertEqual(by_kind["meeting"], ["جلسهٔ هفتگی"])
        self.assertEqual(by_kind["action"], ["اقدام من"])
        self.assertEqual(by_kind["audit"], ["ممیزی من"])
        self.assertEqual(by_kind["risk_review"], ["ریسک من"])
        self.assertEqual(len(by_kind["document_review"]), 1)
        self.assertEqual(len(by_kind["leave"]), 1)
        self.assertEqual(by_kind["delegation"], ["جانشین موقت «هوش مصنوعی»"])
        self.assertEqual(by_kind["holiday"], ["تعطیل رسمی"])
        self.assertNotIn("team_leave", by_kind)
        self.assertTrue(body["is_lead"])
        overdue = [i for i in body["items"] if i["overdue"]]
        self.assertEqual([i["kind"] for i in overdue], ["action"])
        self.assertEqual([i["date"] for i in body["items"]], sorted(i["date"] for i in body["items"]))

    def test_the_window_limits_what_is_shown(self):
        titles = [i["title"] for i in self.agenda(self.me, start=4, end=6)["items"]]
        self.assertIn("جلسهٔ هفتگی", titles)
        self.assertNotIn("ریزهدف من", titles)
        self.assertIn("جانشین موقت «هوش مصنوعی»", titles)  # a span overlapping the window

    def test_team_leave_for_a_lead_only_of_their_subtree(self):
        names = [i["title"] for i in self.agenda(self.me, team=True)["items"] if i["kind"] == "team_leave"]
        self.assertEqual(names, ["کارمند"])
        body = self.agenda(self.worker, team=True)
        self.assertFalse(body["is_lead"])
        self.assertFalse(body["team"])
        self.assertNotIn("team_leave", {i["kind"] for i in body["items"]})

    def test_document_reviews_only_for_those_who_may_write_them(self):
        kinds = {i["kind"] for i in self.agenda(self.other)["items"]}
        self.assertNotIn("document_review", kinds)

    def test_bad_windows(self):
        client = APIClient()
        client.force_authenticate(self.me)
        url = reverse("agenda")
        self.assertEqual(client.get(url, {"from": "x", "to": "2026-10-10"}).status_code, 400)
        self.assertEqual(client.get(url, {"from": "2026-10-10", "to": "2026-10-01"}).status_code, 400)
        self.assertEqual(client.get(url, {"from": "2026-10-01", "to": "2026-12-15"}).status_code, 400)
        self.assertEqual(APIClient().get(url, {"from": "2026-10-01", "to": "2026-10-10"}).status_code, 401)
