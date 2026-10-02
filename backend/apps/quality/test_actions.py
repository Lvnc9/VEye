"""Corrective actions, closing and reopening (Phase 18, slice 2)."""
import threading
from datetime import timedelta

from django.db import IntegrityError, connection, transaction
from django.test import TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone

from apps.documents import test_support
from apps.notifications import tasks as notification_tasks
from apps.notifications.models import Notification, NotificationKind
from apps.organization import tree

from . import services
from .models import ActionStatus, CorrectiveAction, NcStatus, NonConformance, QualityEvent, QualityEventKind
from .test_support import LOCMEM, QualityBase, person

TOMORROW = timezone.localdate() + timedelta(days=1)


class ActionBase(QualityBase):
    """A record at RAG that has been accepted (IN_PROGRESS), a plain worker to assign things to, and
    helpers to call the action endpoints."""

    def setUp(self):
        super().setUp()
        self.worker = person(name="کارگر")
        self.worker2 = person(name="کارگر دوم")
        self.nc = self.make()
        services.accept(self.nc, actor=self.rag_lead, root_cause="دلیل")

    def reverse_action(self, name, nc, action):
        return reverse(f"nonconformance-{name}", kwargs={"pk": nc.pk, "action_id": action.pk})

    def add(self, user=None, nc=None, **over):
        body = {"title": "آموزش تیم", "assignee": self.worker.pk, "due_on": (TOMORROW + timedelta(days=5)).isoformat(), **over}
        return self.api(user or self.rag_lead).post(reverse("nonconformance-actions", args=[(nc or self.nc).pk]), body, format="json")

    def make_action(self, nc=None, **over) -> CorrectiveAction:
        response = self.add(nc=nc, **over)
        assert response.status_code == 201, response.data
        return CorrectiveAction.objects.get(pk=response.data["id"])

    def patch(self, user, action, nc=None, **changes):
        return self.api(user).patch(self.reverse_action("action-detail", nc or self.nc, action), changes, format="json")

    def post(self, user, name, action, nc=None, **payload):
        return self.api(user).post(self.reverse_action(f"action-{name}", nc or self.nc, action), payload, format="json")

    def done(self, action):
        """Have the assignee do it: TODO → IN_PROGRESS → DONE."""
        for status in ("IN_PROGRESS", "DONE"):
            assert self.patch(action.assignee, action, status=status).status_code == 200
        action.refresh_from_db()
        return action

    def verified(self, action):
        self.done(action)
        assert self.post(self.ai_lead, "verify", action, note="ok").status_code == 200
        action.refresh_from_db()
        return action

    def close(self, user=None, **over):
        return self.api(user or self.rag_lead).post(
            reverse("nonconformance-close", args=[self.nc.pk]), {"effectiveness_note": "دیگر تکرار نشد", **over}, format="json"
        )

    def told(self, kind):
        return set(Notification.objects.filter(kind=kind).values_list("recipient_id", flat=True))


class AddActionTests(ActionBase):
    def test_a_manager_adds_one_while_the_record_is_in_progress(self):
        response = self.add()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual((response.data["status"], response.data["assignee_name"], response.data["is_overdue"]), ("TODO", "کارگر", False))
        event = QualityEvent.objects.get(kind=QualityEventKind.ACTION_ADDED)
        self.assertEqual((event.subject_title, event.note, event.actor_name), ("آموزش تیم", "کارگر", self.rag_lead.full_name))

    def test_the_assignee_is_told_unless_they_assigned_it_to_themselves(self):
        self.add()
        note = Notification.objects.get(kind=NotificationKind.CAPA_ASSIGNED)
        self.assertEqual((note.recipient_id, note.url), (self.worker.pk, f"/quality/{self.nc.pk}"))
        self.add(assignee=self.rag_lead.pk)
        self.assertEqual(self.told(NotificationKind.CAPA_ASSIGNED), {self.worker.pk})

    def test_only_a_manager_adds(self):
        self.assertEqual(self.add(user=self.reporter).status_code, 403)
        self.assertEqual(self.add(user=self.worker).status_code, 404)  # cannot even see it yet
        self.assertEqual(CorrectiveAction.objects.count(), 0)

    def test_only_while_in_progress(self):
        open_nc = self.make()
        refused = self.add(nc=open_nc)
        self.assertEqual((refused.status_code, refused.data["code"]), (409, "nc_not_in_progress"))
        rejected = self.make()
        services.reject(rejected, actor=self.rag_lead, reason="x")
        self.assertEqual(self.add(nc=rejected).data["code"], "nc_not_in_progress")

    def test_the_assignee_must_be_active_and_not_the_developer_account(self):
        self.worker.is_active = False
        self.worker.save()
        self.assertEqual(self.add().data["code"], "assignee_not_eligible")
        self.assertEqual(self.add(assignee=self.developer.pk).data["code"], "assignee_not_eligible")

    def test_the_deadline_may_be_today_but_not_the_past(self):
        self.assertEqual(self.add(due_on=timezone.localdate().isoformat()).status_code, 201)
        past = self.add(due_on=(timezone.localdate() - timedelta(days=1)).isoformat())
        self.assertEqual((past.status_code, past.data["code"]), (409, "due_in_past"))

    def test_a_title_is_required(self):
        self.assertEqual(self.add(title="  ").status_code, 400)

    def test_the_list_shows_every_action_cancelled_ones_included_soonest_first(self):
        late = self.make_action(title="دیرتر", due_on=(TOMORROW + timedelta(days=9)).isoformat())
        soon = self.make_action(title="زودتر", due_on=TOMORROW.isoformat())
        self.post(self.rag_lead, "cancel", late, reason="لازم نیست")
        rows = self.api(self.reporter).get(reverse("nonconformance-actions", args=[self.nc.pk])).data
        self.assertEqual([(r["title"], r["status"]) for r in rows], [("زودتر", "TODO"), ("دیرتر", "CANCELLED")])


class AssigneeTests(ActionBase):
    def test_the_assignee_moves_it_along_and_only_that(self):
        action = self.make_action()
        for status, expected in (("IN_PROGRESS", 200), ("DONE", 200)):
            self.assertEqual(self.patch(self.worker, action, status=status).status_code, expected, status)
        action.refresh_from_db()
        self.assertEqual(action.status, ActionStatus.DONE)
        self.assertIsNotNone(action.completed_at)

    def test_an_assignee_cannot_touch_anything_but_the_status(self):
        action = self.make_action()
        for change in ({"title": "x"}, {"due_on": (TOMORROW + timedelta(days=30)).isoformat()}, {"assignee": self.worker2.pk}, {"status": "IN_PROGRESS", "title": "x"}):
            self.assertEqual(self.patch(self.worker, action, **change).status_code, 403, change)
        action.refresh_from_db()
        self.assertEqual((action.title, action.status), ("آموزش تیم", ActionStatus.TODO))

    def test_someone_else_cannot_move_it(self):
        action = self.make_action()
        self.assertEqual(self.patch(self.worker2, action, status="IN_PROGRESS").status_code, 404)  # invisible to them
        self.assertEqual(self.patch(self.reporter, action, status="IN_PROGRESS").status_code, 403)  # visible, not theirs

    def test_the_graph_has_no_shortcuts(self):
        action = self.make_action()
        response = self.patch(self.worker, action, status="DONE")  # TODO → DONE skips the work
        self.assertEqual((response.status_code, response.data["code"]), (409, "invalid_transition"))
        self.assertEqual(self.patch(self.worker, action, status="VERIFIED").status_code, 400)  # not offered at all
        self.assertEqual(self.patch(self.worker, action, status="CANCELLED").status_code, 400)

    def test_stepping_back_before_verification_clears_the_completion_time(self):
        action = self.done(self.make_action())
        self.assertEqual(self.patch(self.worker, action, status="IN_PROGRESS").status_code, 200)
        action.refresh_from_db()
        self.assertIsNone(action.completed_at)

    def test_a_manager_may_move_it_for_them(self):
        action = self.make_action()
        self.assertEqual(self.patch(self.rag_lead, action, status="IN_PROGRESS").status_code, 200)

    def test_the_assignee_can_now_see_the_record_and_it_is_in_their_assigned_list(self):
        action = self.make_action()
        self.assertEqual(self.api(self.worker).get(reverse("nonconformance-detail", args=[self.nc.pk])).status_code, 200)
        rows = self.api(self.worker).get(reverse("nonconformance-list"), {"mine": "assigned"}).data["results"]
        self.assertEqual([r["id"] for r in rows], [self.nc.pk])
        self.patch(self.rag_lead, action, assignee=self.worker2.pk)  # reassigned away: visibility goes with it
        self.assertEqual(self.api(self.worker).get(reverse("nonconformance-detail", args=[self.nc.pk])).status_code, 404)

    def test_each_change_is_recorded_with_before_and_after(self):
        action = self.make_action()
        self.patch(self.worker, action, status="IN_PROGRESS")
        event = QualityEvent.objects.get(kind=QualityEventKind.ACTION_STATUS_CHANGED)
        self.assertEqual((event.from_status, event.to_status, event.action_id), ("TODO", "IN_PROGRESS", action.pk))

    def test_a_finished_action_is_immutable(self):
        action = self.verified(self.make_action())
        for payload in ({"status": "IN_PROGRESS"}, {"title": "x"}):
            response = self.patch(self.rag_lead, action, **payload)
            self.assertEqual((response.status_code, response.data["code"]), (409, "wrong_status"), payload)

    def test_marking_it_done_tells_the_verifiers_but_never_the_assignee(self):
        action = self.make_action(assignee=self.rag_lead.pk)  # a manager doing the work themselves
        self.done(action)
        self.assertEqual(self.told(NotificationKind.CAPA_READY_TO_VERIFY), {self.ai_lead.pk})  # not rag_lead, who did it

    def test_a_manager_can_edit_the_rest_and_the_changes_are_logged(self):
        action = self.make_action()
        self.assertEqual(self.patch(self.rag_lead, action, title="عنوان تازه", description="شرح").status_code, 200)
        self.assertEqual(QualityEvent.objects.get(kind=QualityEventKind.ACTION_EDITED).note, "عنوان، شرح")
        new_due = (TOMORROW + timedelta(days=20)).isoformat()
        self.patch(self.rag_lead, action, due_on=new_due)
        due = QualityEvent.objects.get(kind=QualityEventKind.ACTION_DUE_CHANGED)
        self.assertEqual(due.to_status, new_due)
        self.assertEqual(self.patch(self.rag_lead, action, due_on=(timezone.localdate() - timedelta(days=1)).isoformat()).data["code"], "due_in_past")
        action.refresh_from_db()
        self.patch(self.rag_lead, action, title=action.title)  # nothing changed: nothing recorded
        self.assertEqual(QualityEvent.objects.filter(kind=QualityEventKind.ACTION_EDITED).count(), 1)

    def test_reassigning_tells_the_new_assignee_and_checks_they_are_eligible(self):
        action = self.make_action()
        self.assertEqual(self.patch(self.rag_lead, action, assignee=self.worker2.pk).status_code, 200)
        self.assertEqual(self.told(NotificationKind.CAPA_ASSIGNED), {self.worker.pk, self.worker2.pk})
        self.assertEqual(QualityEvent.objects.get(kind=QualityEventKind.ACTION_ASSIGNED).note, "کارگر ← کارگر دوم")
        self.assertEqual(self.patch(self.rag_lead, action, assignee=self.developer.pk).data["code"], "assignee_not_eligible")

    def test_an_action_of_another_record_is_a_404(self):
        other = self.make()
        services.accept(other, actor=self.rag_lead, root_cause="x")
        action = self.make_action(nc=other)
        self.assertEqual(self.patch(self.rag_lead, action, nc=self.nc, status="IN_PROGRESS").status_code, 404)


class VerificationTests(ActionBase):
    def test_a_different_manager_verifies_a_done_action(self):
        action = self.done(self.make_action())
        response = self.post(self.ai_lead, "verify", action, note="دیدم و درست است")
        self.assertEqual(response.status_code, 200, response.data)
        action.refresh_from_db()
        self.assertEqual((action.status, action.verified_by_id, action.verification_note), (ActionStatus.VERIFIED, self.ai_lead.pk, "دیدم و درست است"))
        self.assertIsNotNone(action.verified_at)
        self.assertEqual(self.told(NotificationKind.CAPA_VERIFIED), {self.worker.pk})

    def test_whoever_did_the_work_cannot_verify_it_even_the_ceo(self):
        action = self.make_action(assignee=self.ceo.pk)
        self.done(action)
        for who in (self.ceo,):
            response = self.post(who, "verify", action)
            self.assertEqual((response.status_code, response.data["code"]), (409, "self_verification"))
            self.assertEqual(self.post(who, "fail-verification", action, reason="x").data["code"], "self_verification")
        self.assertEqual(self.post(self.ai_lead, "verify", action).status_code, 200)  # another manager can

    def test_the_assignee_who_is_not_a_manager_is_simply_refused(self):
        action = self.done(self.make_action())
        self.assertEqual(self.post(self.worker, "verify", action).status_code, 403)

    def test_only_a_done_action_is_verified(self):
        action = self.make_action()
        response = self.post(self.ai_lead, "verify", action)
        self.assertEqual((response.status_code, response.data["code"]), (409, "wrong_status"))
        self.assertEqual(self.post(self.ai_lead, "fail-verification", action, reason="x").status_code, 409)

    def test_a_failed_verification_sends_it_back_with_the_reason(self):
        action = self.done(self.make_action())
        self.assertEqual(self.post(self.ai_lead, "fail-verification", action, reason="").status_code, 400)
        self.assertEqual(self.post(self.ai_lead, "fail-verification", action, reason="هنوز تکرار می‌شود").status_code, 200)
        action.refresh_from_db()
        self.assertEqual((action.status, action.completed_at), (ActionStatus.IN_PROGRESS, None))
        event = QualityEvent.objects.get(kind=QualityEventKind.ACTION_VERIFICATION_FAILED)
        self.assertEqual((event.from_status, event.to_status, event.note), ("DONE", "IN_PROGRESS", "هنوز تکرار می‌شود"))
        self.assertEqual(self.told(NotificationKind.CAPA_VERIFICATION_FAILED), {self.worker.pk})

    def test_the_flags_agree_with_the_rules(self):
        action = self.done(self.make_action(assignee=self.rag_lead.pk))
        rows = lambda user: {r["id"]: r for r in self.api(user).get(reverse("nonconformance-actions", args=[self.nc.pk])).data}[action.pk]
        self.assertFalse(rows(self.rag_lead)["can_verify"])  # they did it
        self.assertTrue(rows(self.ai_lead)["can_verify"])
        self.assertFalse(rows(self.reporter)["can_verify"])

    def test_the_database_refuses_a_verified_action_without_a_time(self):
        action = self.make_action()
        with self.assertRaises(IntegrityError), transaction.atomic():
            CorrectiveAction.objects.filter(pk=action.pk).update(status=ActionStatus.VERIFIED)


class CancelTests(ActionBase):
    def test_a_manager_cancels_with_a_reason_and_it_stops_counting(self):
        action = self.make_action()
        self.assertEqual(self.post(self.rag_lead, "cancel", action, reason="").status_code, 400)
        self.assertEqual(self.post(self.rag_lead, "cancel", action, reason="دیگر لازم نیست").status_code, 200)
        action.refresh_from_db()
        self.assertEqual((action.status, action.cancel_reason), (ActionStatus.CANCELLED, "دیگر لازم نیست"))
        self.assertEqual(self.told(NotificationKind.CAPA_CANCELLED), {self.worker.pk})
        data = self.api(self.rag_lead).get(reverse("nonconformance-detail", args=[self.nc.pk])).data
        self.assertEqual(data["actions_total"], 0)

    def test_the_assignee_cannot_cancel_their_own_action(self):
        action = self.make_action()
        self.assertEqual(self.post(self.worker, "cancel", action, reason="x").status_code, 403)

    def test_a_verified_or_cancelled_action_cannot_be_cancelled(self):
        verified = self.verified(self.make_action())
        self.assertEqual(self.post(self.rag_lead, "cancel", verified, reason="x").data["code"], "wrong_status")
        gone = self.make_action(title="ب")
        self.post(self.rag_lead, "cancel", gone, reason="x")
        self.assertEqual(self.post(self.rag_lead, "cancel", gone, reason="x").status_code, 409)


class DerivedCountsTests(ActionBase):
    def counts(self):
        data = self.api(self.rag_lead).get(reverse("nonconformance-detail", args=[self.nc.pk])).data
        return data["actions_total"], data["actions_verified"], data["actions_overdue"]

    def test_the_counts_are_derived_and_exclude_cancelled(self):
        self.assertEqual(self.counts(), (0, 0, 0))
        a, b, c = (self.make_action(title=t) for t in "abc")
        self.verified(a)
        self.post(self.rag_lead, "cancel", c, reason="x")
        self.assertEqual(self.counts(), (2, 1, 0))

    def test_overdue_means_still_the_assignees_to_do_and_past_its_deadline(self):
        todo, in_progress, done = (self.make_action(title=t) for t in ("t", "p", "d"))
        self.patch(self.worker, in_progress, status="IN_PROGRESS")
        self.done(done)
        past = timezone.localdate() - timedelta(days=3)
        CorrectiveAction.objects.update(due_on=past)
        self.assertEqual(self.counts()[2], 2)  # todo + in progress; the done one waits on a verifier, it is not late
        rows = self.api(self.rag_lead).get(reverse("nonconformance-list"), {"overdue": "1"}).data["results"]
        self.assertEqual([r["id"] for r in rows], [self.nc.pk])
        self.assertEqual(self.api(self.rag_lead).get(reverse("nonconformance-list"), {"overdue": "1", "status": "CLOSED"}).data["count"], 0)

    def test_mine_manage_lists_what_i_manage(self):
        other = person()
        test_support.lead_of(other, self.org.dev)
        sibling = self.make(owner_node=self.org.backend.pk)
        mine = lambda user: [r["id"] for r in self.api(user).get(reverse("nonconformance-list"), {"mine": "manage"}).data["results"]]
        self.assertEqual(mine(self.rag_lead), [self.nc.pk])
        self.assertEqual(mine(other), [sibling.pk])
        self.assertEqual(sorted(mine(self.qm)), sorted([self.nc.pk, sibling.pk]))  # manage_quality manages everything

    def test_there_is_no_query_per_row(self):
        for i in range(4):
            nc = self.make(title=f"سابقه {i}")
            services.accept(nc, actor=self.rag_lead, root_cause="x")
            self.make_action(nc=nc)
        client = self.api(self.rag_lead)
        with self.assertNumQueries(3):  # the viewer's leads, the page count, the page — one each, whatever the rows
            client.get(reverse("nonconformance-list"))


class CloseTests(ActionBase):
    def test_closing_needs_at_least_one_action(self):
        response = self.close()
        self.assertEqual((response.status_code, response.data["code"], response.data["actions"]), (409, "cannot_close", 0))

    def test_closing_needs_every_action_verified_and_says_how_many_are_not(self):
        a, b = self.make_action(title="a"), self.make_action(title="b")
        self.verified(a)
        response = self.close()
        self.assertEqual((response.status_code, response.data["code"]), (409, "cannot_close"))
        self.assertEqual((response.data["actions"], response.data["verified"], response.data["unverified"]), (2, 1, 1))
        self.done(b)  # done but not verified is still not enough
        self.assertEqual(self.close().data["unverified"], 1)

    def test_only_cancelled_actions_do_not_make_a_plan(self):
        action = self.make_action()
        self.post(self.rag_lead, "cancel", action, reason="x")
        self.assertEqual(self.close().data["code"], "cannot_close")

    def test_a_cancelled_action_does_not_block_closing(self):
        self.verified(self.make_action(title="a"))
        self.post(self.rag_lead, "cancel", self.make_action(title="b"), reason="x")
        self.assertEqual(self.close().status_code, 200)

    def test_the_effectiveness_note_is_required(self):
        self.verified(self.make_action())
        self.assertEqual(self.close(effectiveness_note="  ").status_code, 400)
        self.nc.refresh_from_db()
        self.assertEqual(self.nc.status, NcStatus.IN_PROGRESS)

    def test_a_successful_close_records_who_when_and_why_and_tells_the_people_involved(self):
        self.verified(self.make_action())
        response = self.close()
        self.assertEqual(response.status_code, 200, response.data)
        self.nc.refresh_from_db()
        self.assertEqual((self.nc.status, self.nc.effectiveness_note, self.nc.closed_by_id), (NcStatus.CLOSED, "دیگر تکرار نشد", self.rag_lead.pk))
        self.assertIsNotNone(self.nc.closed_at)
        event = QualityEvent.objects.get(kind=QualityEventKind.NC_CLOSED)
        self.assertEqual((event.from_status, event.to_status, event.note), ("IN_PROGRESS", "CLOSED", "دیگر تکرار نشد"))
        self.assertEqual(self.told(NotificationKind.NC_CLOSED), {self.reporter.pk, self.worker.pk})  # not the closer

    def test_only_a_manager_closes_and_only_an_in_progress_record(self):
        self.verified(self.make_action())
        self.assertEqual(self.close(user=self.reporter).status_code, 403)
        self.assertEqual(self.close(user=self.worker).status_code, 403)
        open_nc = self.make()
        response = self.api(self.rag_lead).post(reverse("nonconformance-close", args=[open_nc.pk]), {"effectiveness_note": "x"}, format="json")
        self.assertEqual((response.status_code, response.data["code"]), (409, "wrong_status"))

    def test_the_can_close_flag_mirrors_the_blockers(self):
        action = self.make_action()
        flag = lambda: self.api(self.rag_lead).get(reverse("nonconformance-detail", args=[self.nc.pk])).data["can_close"]
        self.assertFalse(flag())
        self.verified(action)
        self.assertTrue(flag())
        self.assertFalse(self.api(self.reporter).get(reverse("nonconformance-detail", args=[self.nc.pk])).data["can_close"])

    def test_a_closed_record_is_read_only(self):
        action = self.verified(self.make_action())
        self.close()
        self.assertEqual(self.add().data["code"], "nc_not_in_progress")
        self.assertEqual(self.patch(self.rag_lead, action, title="x").data["code"], "nc_not_in_progress")
        edit = self.api(self.rag_lead).patch(reverse("nonconformance-detail", args=[self.nc.pk]), {"title": "x"}, format="json")
        self.assertEqual((edit.status_code, edit.data["code"]), (409, "wrong_status"))


class ReopenClosedTests(ActionBase):
    def closed(self):
        self.verified(self.make_action())
        self.assertEqual(self.close().status_code, 200)

    def reopen(self, user=None, **over):
        return self.api(user or self.rag_lead).post(
            reverse("nonconformance-reopen", args=[self.nc.pk]), {"reason": "مشکل تکرار شد", **over}, format="json"
        )

    def test_reopening_goes_back_to_in_progress_and_clears_the_closing_data(self):
        self.closed()
        self.assertEqual(self.reopen().status_code, 200)
        self.nc.refresh_from_db()
        self.assertEqual((self.nc.status, self.nc.closed_at, self.nc.closed_by_id, self.nc.effectiveness_note), (NcStatus.IN_PROGRESS, None, None, ""))
        event = QualityEvent.objects.get(kind=QualityEventKind.NC_REOPENED)
        self.assertEqual((event.from_status, event.to_status, event.note), ("CLOSED", "IN_PROGRESS", "مشکل تکرار شد"))
        # the closing line keeps the note the record no longer shows
        self.assertEqual(QualityEvent.objects.get(kind=QualityEventKind.NC_CLOSED).note, "دیگر تکرار نشد")

    def test_verified_actions_stay_verified_and_a_new_action_can_be_added(self):
        self.closed()
        self.reopen()
        self.assertEqual(CorrectiveAction.objects.get().status, ActionStatus.VERIFIED)
        self.assertEqual(self.add(title="اقدام تازه").status_code, 201)
        self.assertEqual(self.close().data["code"], "cannot_close")  # the new one is not verified yet

    def test_a_reason_is_required_and_only_a_manager_may(self):
        self.closed()
        self.assertEqual(self.reopen(reason="").status_code, 400)
        self.assertEqual(self.reopen(user=self.reporter).status_code, 403)

    def test_an_in_progress_record_has_nothing_to_reopen(self):
        self.assertEqual(self.reopen().data["code"], "wrong_status")


class DueActionsTaskTests(ActionBase):
    def test_reminds_the_assignee_once_a_day_and_never_twice(self):
        action = self.make_action(due_on=TOMORROW.isoformat())
        self.assertEqual(notification_tasks.check_due_actions(), 1)
        note = Notification.objects.get(kind=NotificationKind.CAPA_DUE_SOON)
        self.assertEqual((note.recipient_id, note.url), (self.worker.pk, f"/quality/{self.nc.pk}"))
        self.assertEqual(notification_tasks.check_due_actions(), 0)  # the dedupe key makes a re-run a no-op
        CorrectiveAction.objects.filter(pk=action.pk).update(due_on=timezone.localdate() - timedelta(days=2))
        self.assertEqual(notification_tasks.check_due_actions(), 1)
        self.assertEqual(Notification.objects.filter(kind=NotificationKind.CAPA_OVERDUE).count(), 1)

    def test_only_what_the_assignee_still_has_to_do_on_a_live_record(self):
        done = self.make_action(title="انجام‌شده", due_on=TOMORROW.isoformat())
        self.done(done)  # waiting on a verifier: nothing to chase
        self.make_action(title="دور", due_on=(TOMORROW + timedelta(days=60)).isoformat())  # not due soon
        self.assertEqual(notification_tasks.check_due_actions(), 0)
        # A *fresh* action on a record that is no longer being worked — a new dedupe key, so a
        # re-run's no-op cannot hide a filter that forgot to look at the record's status.
        other = self.make()
        services.accept(other, actor=self.rag_lead, root_cause="x")
        self.make_action(nc=other, title="تازه", due_on=TOMORROW.isoformat())
        NonConformance.objects.filter(pk=other.pk).update(status=NcStatus.REJECTED)
        self.assertEqual(notification_tasks.check_due_actions(), 0)


class PersonnelAndFeedTests(ActionBase):
    def test_someone_with_an_action_cannot_be_deleted(self):
        self.make_action()
        response = self.api(self.ceo).delete(reverse("personnel-detail", args=[self.worker.pk]))
        self.assertEqual((response.status_code, response.data["code"]), (409, "user_has_quality_records"))

    def test_the_feed_labels_action_statuses_and_leaves_dates_unlabelled(self):
        action = self.make_action()
        self.patch(self.worker, action, status="IN_PROGRESS")
        self.patch(self.rag_lead, action, due_on=(TOMORROW + timedelta(days=9)).isoformat())
        rows = self.api(self.reporter).get(reverse("nonconformance-activity", args=[self.nc.pk])).data["results"]
        by_kind = {r["kind"]: r for r in rows}
        self.assertEqual(by_kind["action_status_changed"]["to_status_label"], ActionStatus.IN_PROGRESS.label)
        self.assertEqual(by_kind["action_due_changed"]["to_status_label"], "")  # an ISO date, not a status
        self.assertEqual(by_kind["nc_accepted"]["to_status_label"], NcStatus.IN_PROGRESS.label)


@override_settings(CACHES=LOCMEM)
@skipUnlessDBFeature("has_select_for_update")
class ConcurrentCloseTests(TransactionTestCase):
    """The close rule is checked under the record's row lock. Without it, closing could count «۱ از ۱
    تایید شده», a second request could add an unverified action in that instant, and the record would
    close with work still open. Whatever the interleaving, a CLOSED record has no unverified action."""

    def run_concurrently(self, worker, n):
        results, barrier = [], threading.Barrier(n)

        def target(i):
            try:
                barrier.wait()
                results.append(("ok", worker(i)))
            except Exception as exc:  # noqa: BLE001 - asserted on below
                results.append(("err", exc))
            finally:
                connection.close()

        threads = [threading.Thread(target=target, args=(i,)) for i in range(n)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        return results

    def test_a_record_is_never_closed_with_an_unverified_action(self):
        org = test_support.ensure_org()
        lead, other, worker, reporter = (person(name=n) for n in ("مسئول", "دیگر", "کارگر", "گزارش"))
        test_support.lead_of(lead, org.rag)
        test_support.lead_of(other, org.ai)
        for attempt in range(6):
            nc = services.report(actor=reporter, title=f"مورد {attempt}", description="شرح", owner_node=org.rag)
            services.accept(nc, actor=lead, root_cause="x")
            first = services.add_action(nc, actor=lead, title="یک", assignee=worker, due_on=TOMORROW)
            services.update_action(nc, first, actor=worker, changes={"status": "IN_PROGRESS"})
            services.update_action(nc, first, actor=worker, changes={"status": "DONE"})
            services.verify_action(nc, first, actor=other)

            def worker_fn(i, nc=nc):
                if i == 0:
                    return services.add_action(nc, actor=lead, title="دو", assignee=worker, due_on=TOMORROW)
                return services.close(nc, actor=lead, effectiveness_note="تمام")

            self.run_concurrently(worker_fn, 2)
            nc.refresh_from_db()
            if nc.status == NcStatus.CLOSED:
                live = nc.actions.exclude(status=ActionStatus.CANCELLED)
                self.assertEqual(live.filter(status=ActionStatus.VERIFIED).count(), live.count(), f"attempt {attempt}")
