"""Leave requests (Phase 19): who asks, who decides (the requester's مسئول or anyone above, a temporary
cover, the مدیر عامل — never the requester), overlap, cancellation, who sees what, the flags. The chart is
documents/test_support's: a worker in the بخش RAG; leads of RAG, of هوش مصنوعی above it, and of the
sibling unit توسعه."""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AccessLevel, AccessRoll, User
from apps.documents import test_support
from apps.notifications.models import Notification, NotificationKind
from apps.organization.models import Delegation, Membership

from .models import LeaveRequest, LeaveStatus

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "veye-leave-tests"}}
_n = [0]


def person(roll=AccessRoll.GUILD, level=AccessLevel.LEVEL_3, name=None, **extra):
    _n[0] += 1
    code = f"94{_n[0]:08d}"
    return User.objects.create_user(
        national_code=code, password="pw-for-tests-123", full_name=name or f"کاربر {code}",
        access_roll=roll, access_level=level, **extra,
    )


def day(offset):
    return (timezone.localdate() + timedelta(days=offset)).isoformat()


@override_settings(CACHES=LOCMEM)
class LeaveBase(TestCase):
    def setUp(self):
        self.org = test_support.ensure_org()
        self.worker = person(name="کارمند")
        test_support.member_of(self.worker, self.org.rag, is_primary=True)
        self.rag_lead = person(name="مسئول RAG")
        test_support.lead_of(self.rag_lead, self.org.rag, is_primary=True)
        self.ai_lead = person(name="مسئول هوش مصنوعی")
        test_support.lead_of(self.ai_lead, self.org.ai)
        self.dev_lead = person(name="مسئول توسعه")
        test_support.lead_of(self.dev_lead, self.org.dev)
        self.hr = person(AccessRoll.EMPLOYER, AccessLevel.LEVEL_2, name="منابع انسانی")  # manage_personnel
        self.ceo = person(AccessRoll.EMPLOYER, AccessLevel.LEVEL_1, name="مدیر عامل")
        self.outsider = person(name="بیرونی")
        self.developer = person(is_developer=True, name="توسعه‌دهنده")
        Notification.objects.all().delete()  # the memberships above told people things

    def api(self, user=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client

    def ask(self, user=None, **over):
        body = {"leave_type": "ANNUAL", "starts_on": day(10), "ends_on": day(12), "reason": "سفر خانوادگی", **over}
        return self.api(user or self.worker).post(reverse("leave-list"), body, format="json")

    def make(self, user=None, **over) -> LeaveRequest:
        response = self.ask(user, **over)
        assert response.status_code == 201, response.data
        return LeaveRequest.objects.get(pk=response.data["id"])

    def act(self, user, leave, name, **body):
        return self.api(user).post(reverse(f"leave-{name}", args=[leave.pk]), body, format="json")

    def told(self, kind):
        return sorted(Notification.objects.filter(kind=kind).values_list("recipient_id", flat=True))


class AskTests(LeaveBase):
    def test_a_request_records_the_unit_and_counts_its_days(self):
        response = self.ask()
        self.assertEqual(response.status_code, 201)
        data = response.data
        self.assertEqual((data["status"], data["node_name"], data["days"], data["leave_type_label"]), ("PENDING", "RAG", 3, "استحقاقی"))
        self.assertEqual((data["can_cancel"], data["can_decide"]), (True, False))

    def test_who_may_ask(self):
        self.assertEqual(self.ask(self.developer).status_code, 403)
        self.assertEqual(self.api().post(reverse("leave-list"), {}, format="json").status_code, 401)
        self.assertEqual(self.ask(self.outsider).status_code, 201)  # no place in the chart: only the مدیر عامل can decide

    def test_validation(self):
        self.assertEqual(self.ask(starts_on=day(5), ends_on=day(4)).status_code, 400)
        self.assertEqual(self.ask(leave_type="HOLIDAY").status_code, 400)
        self.assertEqual(self.ask(starts_on="x").status_code, 400)
        self.assertEqual(self.make(reason="").reason, "")
        self.assertEqual(self.make(user=self.rag_lead, starts_on=day(-3), ends_on=day(-2), leave_type="SICK").days, 2)  # after the fact

    def test_overlapping_requests_are_refused_but_touching_ones_are_fine(self):
        first = self.make(starts_on=day(10), ends_on=day(12))
        response = self.ask(starts_on=day(12), ends_on=day(14))
        self.assertEqual((response.status_code, response.data["code"], response.data["other"]), (409, "leave_overlaps", first.pk))
        self.assertEqual(self.ask(starts_on=day(8), ends_on=day(20)).status_code, 409)  # covering it entirely
        self.assertEqual(self.ask(starts_on=day(13), ends_on=day(14)).status_code, 201)  # the next day
        self.assertEqual(self.ask(self.rag_lead, starts_on=day(10), ends_on=day(12)).status_code, 201)  # someone else

    def test_a_rejected_or_cancelled_request_no_longer_holds_the_days(self):
        rejected = self.make()
        self.act(self.rag_lead, rejected, "reject", note="هم‌زمان با پروژه")
        cancelled = self.make()
        self.act(self.worker, cancelled, "cancel")
        self.assertEqual(self.ask().status_code, 201)

    def test_the_leads_of_the_chain_are_told_never_the_requester(self):
        self.make()
        self.assertEqual(self.told(NotificationKind.LEAVE_REQUESTED), sorted([self.rag_lead.pk, self.ai_lead.pk]))
        Notification.objects.all().delete()
        self.make(self.rag_lead)  # a مسئول's own request goes up
        self.assertEqual(self.told(NotificationKind.LEAVE_REQUESTED), [self.ai_lead.pk])

    def test_with_nobody_to_decide_in_the_chart_the_ceo_is_told(self):
        self.make(self.outsider)
        self.assertEqual(self.told(NotificationKind.LEAVE_REQUESTED), [self.ceo.pk])
        Notification.objects.all().delete()
        Membership.objects.filter(is_lead=True).delete()
        self.make(starts_on=day(30), ends_on=day(31))
        self.assertEqual(self.told(NotificationKind.LEAVE_REQUESTED), [self.ceo.pk])


class DecideTests(LeaveBase):
    def setUp(self):
        super().setUp()
        self.leave = self.make()
        Notification.objects.all().delete()

    def test_who_may_decide(self):
        for decider in (self.rag_lead, self.ai_lead, self.ceo):
            leave = self.make(starts_on=day(40 + decider.pk), ends_on=day(40 + decider.pk))
            self.assertEqual(self.act(decider, leave, "approve").status_code, 200, decider.full_name)
        self.assertEqual(self.act(self.hr, self.leave, "approve").status_code, 403)  # HR reads all, decides nothing
        self.assertEqual(self.act(self.dev_lead, self.leave, "approve").status_code, 404)  # cannot even see it
        self.assertEqual(self.act(self.outsider, self.leave, "approve").status_code, 404)
        self.assertEqual(self.act(self.worker, self.leave, "approve").status_code, 403)

    def test_a_lead_never_decides_their_own_request(self):
        own = self.make(self.rag_lead)
        # Each layer on its own: the flag the screen reads (access.can_decide)…
        self.assertFalse(self.api(self.rag_lead).get(reverse("leave-detail", args=[own.pk])).data["can_decide"])
        # …and the service, which says why in words of its own.
        response = self.act(self.rag_lead, own, "approve")
        self.assertEqual((response.status_code, str(response.data["detail"])), (403, "نمی‌توانید دربارهٔ درخواست مرخصی خودتان تصمیم بگیرید."))
        self.assertEqual(self.act(self.ai_lead, own, "approve").status_code, 200)

    def test_a_temporary_cover_decides_for_the_lead(self):
        cover = person(name="جانشین")
        today = timezone.localdate()
        Delegation.objects.create(node=self.org.rag, delegate=cover, starts_on=today, ends_on=today + timedelta(days=3))
        self.assertEqual(self.act(cover, self.leave, "approve").status_code, 200)

    def test_approval_is_recorded_and_the_requester_told(self):
        response = self.act(self.rag_lead, self.leave, "approve", note="  مرخصی خوش  ")
        self.assertEqual((response.data["status"], response.data["decided_by_name"], response.data["decision_note"]), ("APPROVED", self.rag_lead.full_name, "مرخصی خوش"))
        self.assertEqual(self.told(NotificationKind.LEAVE_APPROVED), [self.worker.pk])
        again = self.act(self.ai_lead, self.leave, "reject", note="x")
        self.assertEqual((again.status_code, again.data["code"]), (409, "wrong_status"))

    def test_a_refusal_needs_a_reason(self):
        for body in ({}, {"note": "   "}):
            self.assertEqual(self.act(self.rag_lead, self.leave, "reject", **body).status_code, 400, body)
        self.leave.refresh_from_db()
        self.assertEqual((self.leave.status, Notification.objects.count()), (LeaveStatus.PENDING, 0))
        self.assertEqual(self.act(self.rag_lead, self.leave, "reject", note="هم‌زمان با تحویل پروژه").data["status"], "REJECTED")
        self.assertEqual(self.told(NotificationKind.LEAVE_REJECTED), [self.worker.pk])

    def test_every_flag_agrees_with_its_endpoint(self):
        for viewer in (self.rag_lead, self.ai_lead, self.ceo, self.hr, self.worker):
            leave = self.make(starts_on=day(60 + viewer.pk), ends_on=day(60 + viewer.pk))
            offered = self.api(viewer).get(reverse("leave-detail", args=[leave.pk])).data["can_decide"]
            worked = self.act(viewer, leave, "approve").status_code == 200
            self.assertEqual(offered, worked, viewer.full_name)


class CancelTests(LeaveBase):
    def test_the_requester_cancels_a_pending_request(self):
        leave = self.make()
        self.assertEqual(self.act(self.rag_lead, leave, "cancel").status_code, 403)
        self.assertEqual(self.act(self.worker, leave, "cancel").data["status"], "CANCELLED")
        self.assertEqual(self.act(self.worker, leave, "cancel").status_code, 409)

    def test_an_approved_leave_can_be_cancelled_until_it_starts_and_the_approver_is_told(self):
        future = self.make()
        self.act(self.rag_lead, future, "approve")
        Notification.objects.all().delete()
        self.assertEqual(self.act(self.worker, future, "cancel").data["status"], "CANCELLED")
        self.assertEqual(self.told(NotificationKind.LEAVE_CANCELLED), [self.rag_lead.pk])
        begun = self.make(starts_on=day(0), ends_on=day(2))
        self.act(self.rag_lead, begun, "approve")
        self.assertFalse(self.api(self.worker).get(reverse("leave-detail", args=[begun.pk])).data["can_cancel"])
        response = self.act(self.worker, begun, "cancel")
        self.assertEqual((response.status_code, response.data["code"]), (409, "leave_started"))

    def test_a_rejected_request_cannot_be_cancelled(self):
        leave = self.make()
        self.act(self.rag_lead, leave, "reject", note="x")
        self.assertFalse(self.api(self.worker).get(reverse("leave-detail", args=[leave.pk])).data["can_cancel"])
        self.assertEqual(self.act(self.worker, leave, "cancel").status_code, 409)


class VisibilityTests(LeaveBase):
    def test_who_reads_what(self):
        mine = self.make()
        lead_own = self.make(self.rag_lead)
        far = self.make(self.outsider)
        see = lambda user: {r["id"] for r in self.api(user).get(reverse("leave-list")).data["results"]}
        self.assertEqual(see(self.worker), {mine.pk})
        self.assertEqual(see(self.rag_lead), {mine.pk, lead_own.pk})
        self.assertEqual(see(self.ai_lead), {mine.pk, lead_own.pk})
        self.assertEqual(see(self.dev_lead), set())
        self.assertEqual(see(self.hr), {mine.pk, lead_own.pk, far.pk})
        self.assertEqual(see(self.ceo), {mine.pk, lead_own.pk, far.pk})
        self.assertEqual(see(self.outsider), {far.pk})
        self.assertEqual(self.api(self.dev_lead).get(reverse("leave-detail", args=[mine.pk])).status_code, 404)

    def test_the_filters(self):
        mine = self.make()
        own = self.make(self.rag_lead)
        decided = self.make(starts_on=day(30), ends_on=day(30))
        self.act(self.rag_lead, decided, "approve")
        ids = lambda user, **p: {r["id"] for r in self.api(user).get(reverse("leave-list"), p).data["results"]}
        self.assertEqual(ids(self.rag_lead, to_decide=1), {mine.pk})  # not their own, not the decided one
        self.assertEqual(ids(self.ai_lead, to_decide=1), {mine.pk, own.pk})
        self.assertEqual(ids(self.ceo, to_decide=1), {mine.pk, own.pk})
        self.assertEqual(ids(self.hr, to_decide=1), set())  # HR reads all, decides nothing
        self.assertEqual(ids(self.rag_lead, mine=1), {own.pk})
        self.assertEqual(ids(self.ceo, status="APPROVED"), {decided.pk})
        self.assertEqual(ids(self.ceo, status="bogus"), set())
        self.assertEqual(ids(self.ceo, q="مسئول RAG"), {own.pk})


class GuardTests(LeaveBase):
    def test_a_person_with_leave_history_cannot_be_deleted(self):
        lone = person()
        self.make(lone)
        response = self.api(self.ceo).delete(reverse("personnel-detail", args=[lone.pk]))
        self.assertEqual((response.status_code, response.data["code"]), (409, "user_has_leave_requests"))

    def test_the_database_refuses_an_end_before_the_start_and_a_decision_without_a_time(self):
        leave = self.make()
        with self.assertRaises(IntegrityError), transaction.atomic():
            LeaveRequest.objects.filter(pk=leave.pk).update(ends_on=timezone.localdate() - timedelta(days=30))
        with self.assertRaises(IntegrityError), transaction.atomic():
            LeaveRequest.objects.filter(pk=leave.pk).update(status=LeaveStatus.APPROVED)
