"""Internal audits (Phase 18, slice 5): who may plan, run and read one, the state machine, the findings
that are non-conformances in disguise, and the history. The chart is `test_support.AuditBase`'s: audits
are over «هوش مصنوعی», so its مسئول can read them and the مسئول of its بخش RAG — beneath it — cannot."""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.urls import reverse
from django.utils import timezone

from apps.notifications.models import Notification, NotificationKind
from apps.organization import tree

from .models import AuditStatus, InternalAudit, NcSource, NcStatus, NonConformance, QualityEventKind
from .test_support import AuditBase, person


def _told(kind):
    return list(Notification.objects.filter(kind=kind).order_by("id").values_list("recipient_id", flat=True))


class PlanTests(AuditBase):
    def test_only_manage_quality_plans_an_audit(self):
        for who in (self.qm, self.ceo):
            self.assertEqual(self.api(who).post(reverse("audit-list"), self.audit_body(), format="json").status_code, 201)
        InternalAudit.objects.all().delete()
        # Leading the audited unit is no help: planning is an independent function.
        for who in (self.ai_lead, self.rag_lead, self.reporter, self.auditor, self.outsider, self.developer):
            response = self.api(who).post(reverse("audit-list"), self.audit_body(), format="json")
            self.assertEqual(response.status_code, 403, who.full_name)
        self.assertEqual(self.api().post(reverse("audit-list"), self.audit_body(), format="json").status_code, 401)
        self.assertEqual(InternalAudit.objects.count(), 0)

    def test_the_code_comes_from_the_id_and_the_new_audit_starts_planned(self):
        audit = self.plan()
        data = self.api(self.qm).get(self.audit_url("audit-detail", audit)).data
        self.assertEqual((data["code"], data["status"], data["scope_node_name"]), (f"AU-{audit.pk:04d}", "PLANNED", "هوش مصنوعی"))
        self.assertEqual((data["findings_total"], data["findings_open"]), (0, 0))
        self.assertEqual(
            (data["can_edit"], data["can_change_auditor"], data["can_cancel"], data["can_start"], data["can_complete"], data["can_raise_finding"]),
            (True, True, True, True, False, False),
        )

    def test_the_title_is_required_and_normalised(self):
        for bad in ({"title": "  "}, {"title": ""}):
            self.assertEqual(self.api(self.qm).post(reverse("audit-list"), self.audit_body(**bad), format="json").status_code, 400)
        self.assertEqual(self.plan(title="ممیزي   داخلی").title, "ممیزی داخلی")  # Arabic yeh folded, spaces collapsed

    def test_the_planned_date_cannot_be_in_the_past_but_today_is_fine(self):
        yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
        response = self.api(self.qm).post(reverse("audit-list"), self.audit_body(planned_on=yesterday), format="json")
        self.assertEqual((response.status_code, response.data["code"]), (409, "planned_in_past"))
        self.assertEqual(self.plan(planned_on=timezone.localdate().isoformat()).planned_on, timezone.localdate())

    def test_an_archived_node_cannot_be_audited(self):
        tree.archive_node(self.org.rag)
        response = self.api(self.qm).post(reverse("audit-list"), self.audit_body(scope_node=self.org.rag.pk), format="json")
        self.assertEqual((response.status_code, response.data["code"]), (409, "node_archived"))
        self.assertEqual(InternalAudit.objects.count(), 0)

    def test_the_auditor_must_be_someone_who_can_act(self):
        for bad in (person(is_active=False), self.developer):
            response = self.api(self.qm).post(reverse("audit-list"), self.audit_body(lead_auditor=bad.pk), format="json")
            self.assertEqual((response.status_code, response.data["code"]), (409, "auditor_not_eligible"))
        self.assertEqual(InternalAudit.objects.count(), 0)

    def test_planning_is_recorded_and_the_auditor_and_the_scope_leads_are_told(self):
        audit = self.plan()
        self.assertEqual(self.audit_kinds(audit), [QualityEventKind.AUDIT_PLANNED])
        event = audit.events.get()
        self.assertEqual((event.actor_name, event.to_status, event.note), (self.qm.full_name, "PLANNED", self.auditor.full_name))
        self.assertEqual(sorted(_told(NotificationKind.AUDIT_PLANNED)), sorted([self.auditor.pk, self.ai_lead.pk]))  # not the planner
        self.assertTrue(all(n.url == f"/quality/audits/{audit.pk}" for n in Notification.objects.filter(kind=NotificationKind.AUDIT_PLANNED)))

    def test_an_auditor_who_also_leads_the_scope_is_told_once(self):
        self.plan(lead_auditor=self.ai_lead.pk)
        self.assertEqual(_told(NotificationKind.AUDIT_PLANNED), [self.ai_lead.pk])

    def test_a_refused_plan_leaves_no_trace(self):
        notifications = Notification.objects.count()  # the fixture's memberships already told people things
        self.api(self.qm).post(reverse("audit-list"), self.audit_body(planned_on="2001-01-01"), format="json")
        self.api(self.ai_lead).post(reverse("audit-list"), self.audit_body(), format="json")
        self.assertEqual((InternalAudit.objects.count(), Notification.objects.count()), (0, notifications))


class VisibilityTests(AuditBase):
    def setUp(self):
        super().setUp()
        self.audit = self.plan()
        self.other_auditor = person(name="ممیز دیگر")
        self.elsewhere = self.plan(title="ممیزی توسعه", scope_node=self.org.dev.pk, lead_auditor=self.other_auditor.pk)

    def see(self, user):
        return {row["id"] for row in self.api(user).get(reverse("audit-list")).data["results"]}

    def test_who_reads_what(self):
        everything = {self.audit.pk, self.elsewhere.pk}
        self.assertEqual(self.see(self.qm), everything)
        self.assertEqual(self.see(self.ceo), everything)
        self.assertEqual(self.see(self.auditor), {self.audit.pk})  # the audits they lead
        self.assertEqual(self.see(self.ai_lead), {self.audit.pk})  # leads the audited unit
        self.assertEqual(self.see(self.dev_lead), {self.elsewhere.pk})
        for nobody in (self.rag_lead, self.reporter, self.outsider, self.developer):
            self.assertEqual(self.see(nobody), set(), nobody.full_name)  # a lead *beneath* the scope sees nothing

    def test_the_lead_of_a_node_above_the_scope_reads_it(self):
        from apps.documents import test_support

        boss = person(name="مسئول IT")
        test_support.lead_of(boss, self.org.it)
        self.assertEqual(self.see(boss), {self.audit.pk, self.elsewhere.pk})  # both are under IT

    def test_an_audit_you_may_not_read_is_a_404_everywhere_never_a_403(self):
        for name in ("audit-detail", "audit-activity"):
            self.assertEqual(self.api(self.rag_lead).get(self.audit_url(name, self.audit)).status_code, 404, name)
        for name in ("audit-start", "audit-complete", "audit-cancel", "audit-findings"):
            self.assertEqual(self.api(self.rag_lead).post(self.audit_url(name, self.audit), {}, format="json").status_code, 404, name)
        self.assertEqual(self.api(self.rag_lead).patch(self.audit_url("audit-detail", self.audit), {"title": "x"}, format="json").status_code, 404)

    def test_the_list_filters(self):
        qm = self.api(self.qm)
        by = lambda **params: {r["id"] for r in qm.get(reverse("audit-list"), params).data["results"]}
        self.assertEqual(by(node=self.org.it.pk), {self.audit.pk, self.elsewhere.pk})  # that node and everything beneath it
        self.assertEqual(by(node=self.org.dev.pk), {self.elsewhere.pk})
        self.assertEqual(by(node="x"), set())
        self.assertEqual(by(status="PLANNED"), {self.audit.pk, self.elsewhere.pk})
        self.assertEqual(by(status="COMPLETED"), set())
        self.assertEqual(by(status="bogus"), set())
        self.assertEqual(by(q="توسعه"), {self.elsewhere.pk})
        self.assertEqual(by(q=self.audit.code), {self.audit.pk})
        self.assertEqual(by(q=str(self.audit.pk)), {self.audit.pk})
        self.assertEqual(by(mine="auditor"), set())  # the planner audits nothing
        mine = lambda user, value: {r["id"] for r in self.api(user).get(reverse("audit-list"), {"mine": value}).data["results"]}
        self.assertEqual(mine(self.auditor, "auditor"), {self.audit.pk})
        self.assertEqual(mine(self.other_auditor, "auditor"), {self.elsewhere.pk})
        self.assertEqual(mine(self.ai_lead, "manage"), {self.audit.pk})  # the audits over the units they lead
        self.assertEqual(mine(self.auditor, "manage"), set())  # leading an audit is not leading its unit
        self.assertEqual(mine(self.qm, "manage"), {self.audit.pk, self.elsewhere.pk})

    def test_the_list_costs_the_same_however_many_audits_there_are(self):
        def cost():
            with CaptureQueriesContext(connection) as queries:
                self.api(self.qm).get(reverse("audit-list"))
            return len(queries)

        before = cost()
        for i in range(5):
            self.plan(title=f"ممیزی {i}")
        self.assertEqual(cost(), before)


class LifecycleTests(AuditBase):
    def test_start_by_the_auditor_or_a_quality_manager(self):
        for who in (self.auditor, self.qm):
            audit = self.plan()
            response = self.api(who).post(self.audit_url("audit-start", audit))
            self.assertEqual((response.status_code, response.data["status"]), (200, "IN_PROGRESS"))
            audit.refresh_from_db()
            self.assertIsNotNone(audit.started_at)
            self.assertEqual(self.audit_kinds(audit), [QualityEventKind.AUDIT_PLANNED, QualityEventKind.AUDIT_STARTED])

    def test_a_reader_who_is_not_the_auditor_cannot_start_it(self):
        audit = self.plan()
        self.assertEqual(self.api(self.ai_lead).post(self.audit_url("audit-start", audit)).status_code, 403)
        audit.refresh_from_db()
        self.assertEqual((audit.status, self.audit_kinds(audit)), (AuditStatus.PLANNED, [QualityEventKind.AUDIT_PLANNED]))

    def test_an_audit_can_only_be_started_once_and_the_event_records_the_move(self):
        audit = self.running()
        response = self.api(self.auditor).post(self.audit_url("audit-start", audit))
        self.assertEqual((response.status_code, response.data["code"]), (409, "wrong_status"))
        event = audit.events.get(kind=QualityEventKind.AUDIT_STARTED)
        self.assertEqual((event.from_status, event.to_status), ("PLANNED", "IN_PROGRESS"))

    def test_starting_before_the_planned_date_is_allowed(self):
        self.assertEqual(self.running(planned_on=(timezone.localdate() + timedelta(days=30)).isoformat()).status, AuditStatus.IN_PROGRESS)

    def test_complete_needs_a_summary_and_a_running_audit(self):
        audit = self.plan()
        url = self.audit_url("audit-complete", audit)
        self.assertEqual(self.api(self.auditor).post(url, {"summary": "ok"}, format="json").status_code, 409)  # not started
        self.api(self.auditor).post(self.audit_url("audit-start", audit))
        for bad in ({}, {"summary": "   "}):
            self.assertEqual(self.api(self.auditor).post(url, bad, format="json").status_code, 400, bad)
        response = self.api(self.auditor).post(url, {"summary": "همه چیز بررسی شد؛ مورد خاصی نبود"}, format="json")
        self.assertEqual((response.status_code, response.data["status"]), (200, "COMPLETED"))
        audit.refresh_from_db()
        self.assertEqual((audit.summary, audit.completed_at is not None), ("همه چیز بررسی شد؛ مورد خاصی نبود", True))
        self.assertEqual(audit.events.get(kind=QualityEventKind.AUDIT_COMPLETED).note, audit.summary)

    def test_the_service_itself_refuses_a_blank_summary(self):
        # The API's serializer already rejects it; the service repeats the rule because it must hold
        # whoever calls it (a script, a later feature).
        from rest_framework.exceptions import ValidationError

        from . import services

        audit = self.running()
        for blank in ("", "   ", None):
            with self.assertRaises(ValidationError):
                services.complete_audit(audit, actor=self.auditor, summary=blank)
        audit.refresh_from_db()
        self.assertEqual(audit.status, AuditStatus.IN_PROGRESS)

    def test_only_the_runner_completes_and_a_finished_audit_is_final(self):
        audit = self.running()
        self.assertEqual(self.api(self.ai_lead).post(self.audit_url("audit-complete", audit), {"summary": "x"}, format="json").status_code, 403)
        self.api(self.qm).post(self.audit_url("audit-complete", audit), {"summary": "x"}, format="json")
        for name, body in (("audit-start", {}), ("audit-complete", {"summary": "y"}), ("audit-cancel", {"reason": "z"})):
            response = self.api(self.qm).post(self.audit_url(name, audit), body, format="json")
            self.assertEqual((response.status_code, response.data["code"]), (409, "wrong_status"), name)

    def test_cancel_is_the_quality_managers_alone_and_needs_a_reason(self):
        audit = self.plan()
        url = self.audit_url("audit-cancel", audit)
        self.assertEqual(self.api(self.auditor).post(url, {"reason": "x"}, format="json").status_code, 403)
        self.assertEqual(self.api(self.ai_lead).post(url, {"reason": "x"}, format="json").status_code, 403)
        self.assertEqual(self.api(self.qm).post(url, {}, format="json").status_code, 400)
        self.assertEqual(self.api(self.qm).post(url, {"reason": "  "}, format="json").status_code, 400)
        self.assertEqual(InternalAudit.objects.get(pk=audit.pk).status, AuditStatus.PLANNED)
        response = self.api(self.qm).post(url, {"reason": "منابع نبود"}, format="json")
        self.assertEqual((response.status_code, response.data["status"], response.data["cancel_reason"]), (200, "CANCELLED", "منابع نبود"))

    def test_a_running_audit_can_be_called_off_and_its_findings_stay(self):
        audit = self.running()
        nc = self.raise_finding(audit)
        self.assertEqual(self.api(self.qm).post(self.audit_url("audit-cancel", audit), {"reason": "لغو"}, format="json").status_code, 200)
        nc.refresh_from_db()
        self.assertEqual((nc.audit_id, nc.status), (audit.pk, NcStatus.OPEN))  # a real problem does not vanish with the audit
        event = audit.events.get(kind=QualityEventKind.AUDIT_CANCELLED)
        self.assertEqual((event.from_status, event.to_status, event.note), ("IN_PROGRESS", "CANCELLED", "لغو"))

    def test_the_auditor_is_told_of_a_cancellation_unless_they_did_it(self):
        audit = self.plan()
        self.api(self.qm).post(self.audit_url("audit-cancel", audit), {"reason": "x"}, format="json")
        self.assertEqual(_told(NotificationKind.AUDIT_CANCELLED), [self.auditor.pk])
        again = self.plan(lead_auditor=self.qm.pk)
        self.api(self.qm).post(self.audit_url("audit-cancel", again), {"reason": "x"}, format="json")
        self.assertEqual(_told(NotificationKind.AUDIT_CANCELLED), [self.auditor.pk])  # the planner-auditor cancelled their own

    def test_the_database_itself_refuses_a_finished_audit_with_no_dates(self):
        audit = self.plan()
        with self.assertRaises(IntegrityError), transaction.atomic():
            InternalAudit.objects.filter(pk=audit.pk).update(status=AuditStatus.COMPLETED)  # no completed_at
        with self.assertRaises(IntegrityError), transaction.atomic():
            InternalAudit.objects.filter(pk=audit.pk).update(status=AuditStatus.IN_PROGRESS)  # no started_at


class EditTests(AuditBase):
    def patch(self, audit, body, user=None):
        return self.api(user or self.qm).patch(self.audit_url("audit-detail", audit), body, format="json")

    def test_only_a_quality_manager_edits(self):
        audit = self.plan()
        for who in (self.auditor, self.ai_lead):
            self.assertEqual(self.patch(audit, {"title": "x"}, who).status_code, 403, who.full_name)
        self.assertEqual(self.patch(audit, {"title": "عنوان تازه"}).data["title"], "عنوان تازه")

    def test_a_planned_audit_can_change_everything_and_the_event_names_what_changed(self):
        audit = self.plan()
        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        response = self.patch(audit, {"title": "تازه", "planned_on": tomorrow, "scope_node": self.org.dev.pk})
        self.assertEqual((response.status_code, response.data["scope_node_name"], response.data["planned_on"]), (200, "توسعه", tomorrow))
        event = audit.events.get(kind=QualityEventKind.AUDIT_EDITED)
        self.assertEqual(event.note, "عنوان، تاریخ برنامه، گرهٔ ممیزی‌شونده")  # in the model's field order

    def test_changing_nothing_records_nothing(self):
        audit = self.plan()
        self.patch(audit, {"title": audit.title, "planned_on": audit.planned_on.isoformat(), "lead_auditor": self.auditor.pk})
        self.assertEqual(self.audit_kinds(audit), [QualityEventKind.AUDIT_PLANNED])

    def test_a_date_that_has_since_passed_is_refused_only_when_it_is_the_one_being_changed(self):
        audit = self.plan()
        yesterday = timezone.localdate() - timedelta(days=1)
        InternalAudit.objects.filter(pk=audit.pk).update(planned_on=yesterday)
        self.assertEqual(self.patch(audit, {"title": "هنوز قابل ویرایش"}).status_code, 200)
        response = self.patch(audit, {"planned_on": (yesterday - timedelta(days=1)).isoformat()})
        self.assertEqual((response.status_code, response.data["code"]), (409, "planned_in_past"))

    def test_an_archived_node_cannot_become_the_scope(self):
        tree.archive_node(self.org.llm)
        response = self.patch(self.plan(), {"scope_node": self.org.llm.pk})
        self.assertEqual((response.status_code, response.data["code"]), (409, "node_archived"))

    def test_changing_the_lead_auditor_is_recorded_and_the_new_one_is_told(self):
        audit = self.plan()
        other = person(name="ممیز دوم")
        Notification.objects.all().delete()
        self.assertEqual(self.patch(audit, {"lead_auditor": other.pk}).data["lead_auditor_name"], "ممیز دوم")
        event = audit.events.get(kind=QualityEventKind.AUDIT_AUDITOR_CHANGED)
        self.assertEqual(event.note, f"{self.auditor.full_name} ← ممیز دوم")
        self.assertEqual(_told(NotificationKind.AUDIT_PLANNED), [other.pk])
        self.assertEqual(self.patch(audit, {"lead_auditor": self.developer.pk}).data["code"], "auditor_not_eligible")

    def test_once_running_only_the_auditor_can_be_replaced(self):
        audit = self.running()
        for field, value in (("title", "x"), ("planned_on", "2099-01-01"), ("scope_node", self.org.dev.pk)):
            response = self.patch(audit, {field: value})
            self.assertEqual(response.status_code, 400, field)
            self.assertIn(field, response.data)
        other = person(name="ممیز دوم")
        self.assertEqual(self.patch(audit, {"lead_auditor": other.pk}).status_code, 200)

    def test_a_finished_or_called_off_audit_is_read_only(self):
        done = self.running()
        self.api(self.auditor).post(self.audit_url("audit-complete", done), {"summary": "x"}, format="json")
        off = self.plan()
        self.api(self.qm).post(self.audit_url("audit-cancel", off), {"reason": "x"}, format="json")
        for audit in (done, off):
            response = self.patch(audit, {"title": "x"})
            self.assertEqual((response.status_code, response.data["code"]), (409, "wrong_status"))
            data = self.api(self.qm).get(self.audit_url("audit-detail", audit)).data
            flags = ("can_edit", "can_change_auditor", "can_cancel", "can_start", "can_complete", "can_raise_finding")
            self.assertEqual([data[flag] for flag in flags], [False] * 6)


class FindingTests(AuditBase):
    def setUp(self):
        super().setUp()
        self.audit = self.running()

    def test_a_finding_is_a_nonconformance_with_the_audit_set(self):
        nc = self.raise_finding(self.audit)
        self.assertEqual(
            (nc.source, nc.audit_id, nc.reported_by_id, nc.owner_node_id, nc.severity, nc.status),
            (NcSource.AUDIT, self.audit.pk, self.auditor.pk, self.org.ai.pk, "MINOR", NcStatus.OPEN),
        )
        data = self.api(self.auditor).get(reverse("nonconformance-detail", args=[nc.pk])).data
        self.assertEqual((data["audit"], data["audit_code"], data["audit_title"]), (self.audit.pk, self.audit.code, self.audit.title))
        plain = self.make()
        self.assertEqual(self.api(self.reporter).get(reverse("nonconformance-detail", args=[plain.pk])).data["audit"], None)

    def test_one_line_in_both_timelines_not_two(self):
        nc = self.raise_finding(self.audit)
        self.assertEqual(self.kinds(nc), [QualityEventKind.FINDING_RAISED])  # no separate nc_reported
        event = nc.events.get()
        self.assertEqual((event.audit_id, event.nc_id, event.to_status, event.note), (self.audit.pk, nc.pk, "OPEN", f"{self.audit.code}: {self.audit.title}"))
        self.assertIn(QualityEventKind.FINDING_RAISED, self.audit_kinds(self.audit))

    def test_the_severity_and_a_node_beneath_the_scope_can_be_chosen(self):
        nc = self.raise_finding(self.audit, severity="MAJOR", owner_node=self.org.rag.pk)
        self.assertEqual((nc.severity, nc.owner_node_id), ("MAJOR", self.org.rag.pk))
        Notification.objects.all().delete()
        self.raise_finding(self.audit, owner_node=self.org.rag.pk)
        self.assertEqual(sorted(_told(NotificationKind.NC_REPORTED)), sorted([self.rag_lead.pk, self.ai_lead.pk]))
        self.assertIn(self.audit.code, Notification.objects.filter(kind=NotificationKind.NC_REPORTED).first().body)

    def test_a_node_outside_the_audited_one_is_refused(self):
        for outside in (self.org.dev, self.org.backend, self.org.it, self.org.root):  # a sibling, its child, the parent, the company
            response = self.api(self.auditor).post(
                self.audit_url("audit-findings", self.audit), self.finding_body(owner_node=outside.pk), format="json"
            )
            self.assertEqual(response.status_code, 400, outside.name)
            self.assertIn("owner_node", response.data)
        self.assertEqual(NonConformance.objects.count(), 0)

    def test_an_archived_node_takes_no_finding(self):
        tree.archive_node(self.org.llm)
        response = self.api(self.auditor).post(
            self.audit_url("audit-findings", self.audit), self.finding_body(owner_node=self.org.llm.pk), format="json"
        )
        self.assertEqual((response.status_code, response.data["code"]), (409, "node_archived"))

    def test_findings_only_while_the_audit_is_running(self):
        planned = self.plan()
        done = self.running()
        self.api(self.auditor).post(self.audit_url("audit-complete", done), {"summary": "x"}, format="json")
        off = self.plan()
        self.api(self.qm).post(self.audit_url("audit-cancel", off), {"reason": "x"}, format="json")
        for audit in (planned, done, off):
            response = self.api(self.qm).post(self.audit_url("audit-findings", audit), self.finding_body(), format="json")
            self.assertEqual((response.status_code, response.data["code"]), (409, "audit_not_in_progress"), audit.status)
        self.assertEqual(NonConformance.objects.count(), 0)

    def test_who_may_raise_one(self):
        url = self.audit_url("audit-findings", self.audit)
        self.assertEqual(self.api(self.ai_lead).post(url, self.finding_body(), format="json").status_code, 403)  # can read it, does not run it
        for nobody in (self.rag_lead, self.reporter, self.outsider, self.developer):
            self.assertEqual(self.api(nobody).post(url, self.finding_body(), format="json").status_code, 404, nobody.full_name)
        self.assertEqual(self.api(self.qm).post(url, self.finding_body(), format="json").status_code, 201)

    def test_validation(self):
        url = self.audit_url("audit-findings", self.audit)
        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        for bad in ({"title": " "}, {"description": ""}, {"detected_on": tomorrow}, {"severity": "HUGE"}):
            self.assertEqual(self.api(self.auditor).post(url, self.finding_body(**bad), format="json").status_code, 400, bad)
        self.assertEqual(NonConformance.objects.count(), 0)

    def test_the_auditor_keeps_sight_of_what_a_quality_manager_raised_for_them(self):
        nc = self.raise_finding(self.audit, user=self.qm)
        self.assertEqual(nc.reported_by_id, self.qm.pk)
        self.assertEqual(self.api(self.auditor).get(reverse("nonconformance-detail", args=[nc.pk])).status_code, 200)
        self.assertEqual(self.api(self.outsider).get(reverse("nonconformance-detail", args=[nc.pk])).status_code, 404)
        other = self.running()  # a different audit has a different auditor
        other.lead_auditor = self.reporter
        other.save()
        self.assertEqual(self.api(self.reporter).get(reverse("nonconformance-detail", args=[nc.pk])).status_code, 404)

    def test_the_audits_findings_are_listed_by_the_audit_filter(self):
        mine = self.raise_finding(self.audit)
        other = self.running()
        theirs = self.raise_finding(other)
        stray = self.make()
        qm = self.api(self.qm)
        ids = lambda **params: {r["id"] for r in qm.get(reverse("nonconformance-list"), params).data["results"]}
        self.assertEqual(ids(audit=self.audit.pk), {mine.pk})
        self.assertEqual(ids(audit=other.pk), {theirs.pk})
        self.assertEqual(ids(audit="x"), set())
        self.assertEqual(ids(), {mine.pk, theirs.pk, stray.pk})

    def test_the_audit_counts_its_findings_and_how_many_are_still_open(self):
        first, second = self.raise_finding(self.audit), self.raise_finding(self.audit)
        data = self.api(self.qm).get(self.audit_url("audit-detail", self.audit)).data
        self.assertEqual((data["findings_total"], data["findings_open"]), (2, 2))
        from . import services

        services.reject(second, actor=self.ai_lead, reason="تکراری")
        data = self.api(self.qm).get(self.audit_url("audit-detail", self.audit)).data
        self.assertEqual((data["findings_total"], data["findings_open"]), (2, 1))
        self.assertEqual(first.status, NcStatus.OPEN)

    def test_a_refused_finding_leaves_no_event_and_no_notification(self):
        Notification.objects.all().delete()
        before = self.audit_kinds(self.audit)
        self.api(self.auditor).post(self.audit_url("audit-findings", self.audit), self.finding_body(owner_node=self.org.dev.pk), format="json")
        self.api(self.ai_lead).post(self.audit_url("audit-findings", self.audit), self.finding_body(), format="json")
        self.assertEqual((self.audit_kinds(self.audit), Notification.objects.count()), (before, 0))


class FeedTests(AuditBase):
    def setUp(self):
        super().setUp()
        self.audit = self.running()
        self.nc = self.raise_finding(self.audit)

    def rows(self, user, name, *args, **params):
        return self.api(user).get(reverse(name, args=args), params).data["results"]

    def test_an_audits_history_reads_newest_first_with_the_status_words(self):
        rows = self.rows(self.auditor, "audit-activity", self.audit.pk)
        self.assertEqual([r["kind"] for r in rows], ["finding_raised", "audit_started", "audit_planned"])
        by_kind = {r["kind"]: r for r in rows}
        self.assertEqual(by_kind["audit_started"]["to_status_label"], AuditStatus.IN_PROGRESS.label)
        self.assertEqual(by_kind["audit_planned"]["to_status_label"], AuditStatus.PLANNED.label)
        self.assertEqual(by_kind["finding_raised"]["to_status_label"], NcStatus.OPEN.label)
        self.assertEqual((by_kind["finding_raised"]["nc_code"], by_kind["finding_raised"]["audit_code"]), (self.nc.code, self.audit.code))
        self.assertEqual(by_kind["audit_started"]["audit_title"], self.audit.title)

    def test_the_finding_is_also_the_records_first_line(self):
        rows = self.rows(self.auditor, "nonconformance-activity", self.nc.pk)
        self.assertEqual([(r["kind"], r["audit_code"]) for r in rows], [("finding_raised", self.audit.code)])

    def test_a_history_you_may_not_read_is_a_404(self):
        for nobody in (self.rag_lead, self.outsider):
            self.assertEqual(self.api(nobody).get(reverse("audit-activity", args=[self.audit.pk])).status_code, 404)

    def test_the_cross_feed_covers_the_audits_you_may_read(self):
        elsewhere = self.plan(title="ممیزی توسعه", scope_node=self.org.dev.pk)
        kinds = lambda user, **p: [(r["kind"], r["audit"]) for r in self.rows(user, "quality-activity", **p)]
        everything = kinds(self.qm)
        self.assertIn(("audit_planned", elsewhere.pk), everything)
        self.assertIn(("audit_started", self.audit.pk), everything)
        self.assertEqual(sum(1 for kind, _ in everything if kind == "finding_raised"), 1)  # the OR of two scopes does not repeat the row
        self.assertEqual({a for _, a in kinds(self.ai_lead) if a}, {self.audit.pk})  # not the other unit's audit
        self.assertEqual({a for _, a in kinds(self.dev_lead) if a}, {elsewhere.pk})
        self.assertEqual(kinds(self.outsider), [])
        self.assertEqual({a for _, a in kinds(self.qm, audit=elsewhere.pk)}, {elsewhere.pk})
        self.assertEqual(kinds(self.outsider, audit=self.audit.pk), [])
        self.assertEqual(kinds(self.qm, audit="x"), [])


class GuardTests(AuditBase):
    def test_an_audited_node_cannot_be_deleted_and_says_how_many(self):
        self.plan(scope_node=self.org.llm.pk)
        response = self.api(self.ceo).delete(reverse("org-node-detail", args=[self.org.llm.pk]))
        self.assertEqual((response.status_code, response.data["code"], response.data["audits"]), (409, "node_not_empty", 1))

    def test_a_person_who_leads_an_audit_cannot_be_deleted(self):
        self.plan()
        response = self.api(self.ceo).delete(reverse("personnel-detail", args=[self.auditor.pk]))
        self.assertEqual((response.status_code, response.data["code"]), (409, "user_has_quality_records"))
        self.assertTrue(type(self.auditor).objects.filter(pk=self.auditor.pk).exists())


class FlagTests(AuditBase):
    """The `can_*` flags are what the screen's buttons are drawn from, so each must say exactly what the
    endpoint behind it will do — for every kind of viewer, in every state it matters."""

    def attempt(self, flag, audit, user):
        api = self.api(user)
        if flag == "can_start":
            return api.post(self.audit_url("audit-start", audit))
        if flag == "can_complete":
            return api.post(self.audit_url("audit-complete", audit), {"summary": "x"}, format="json")
        if flag == "can_cancel":
            return api.post(self.audit_url("audit-cancel", audit), {"reason": "x"}, format="json")
        if flag == "can_edit":
            return api.patch(self.audit_url("audit-detail", audit), {"title": "عنوان دیگر"}, format="json")
        if flag == "can_change_auditor":
            replacement = person(name="ممیز جایگزین")
            return api.patch(self.audit_url("audit-detail", audit), {"lead_auditor": replacement.pk}, format="json")
        return api.post(self.audit_url("audit-findings", audit), self.finding_body(), format="json")

    def test_every_flag_agrees_with_its_endpoint(self):
        states = {
            "PLANNED": (self.plan, ["can_start", "can_edit", "can_change_auditor", "can_cancel", "can_complete", "can_raise_finding"]),
            "IN_PROGRESS": (self.running, ["can_start", "can_complete", "can_raise_finding", "can_edit", "can_change_auditor", "can_cancel"]),
        }
        for state, (prepare, flags) in states.items():
            for viewer in (self.qm, self.ceo, self.auditor, self.ai_lead):
                for flag in flags:
                    audit = prepare()
                    offered = self.api(viewer).get(self.audit_url("audit-detail", audit)).data[flag]
                    worked = self.attempt(flag, audit, viewer).status_code in (200, 201)
                    self.assertEqual(offered, worked, f"{state} / {viewer.full_name} / {flag}")

    def test_a_running_audit_offers_no_edit_of_the_plan_but_still_a_change_of_auditor(self):
        data = self.api(self.qm).get(self.audit_url("audit-detail", self.running())).data
        self.assertEqual((data["can_edit"], data["can_change_auditor"], data["can_cancel"]), (False, True, True))
