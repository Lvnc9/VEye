"""Quality figures in Reports (Phase 18, slice 9): the `quality` block of `GET /reports/kpi/` and the
non-conformance export. Built through the real services (report → accept → action → verify → close), with
timestamps moved back only where a test is about age or the window."""
import csv
import io
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from apps.quality import services
from apps.quality.models import CorrectiveAction, InternalAudit, NonConformance, RiskItem
from apps.quality.test_support import AuditBase, RiskBase, person

from .csv_export import BOM


def _rows(response):
    body = b"".join(response.streaming_content).decode("utf-8")
    assert body.startswith(BOM)
    return list(csv.reader(io.StringIO(body[len(BOM):])))


def _ago(days):
    return timezone.now() - timedelta(days=days)


class QualityReportBase(RiskBase, AuditBase):
    def setUp(self):
        super().setUp()
        self.worker = person(name="کارگر")

    def kpi(self, days=90):
        response = self.api(self.qm).get(reverse("reports-kpi"), {"days": days})
        assert response.status_code == 200, response.data
        return response.data["quality"]

    def accepted(self, **over):
        nc = self.make(**over)
        return services.accept(nc, actor=self.rag_lead, root_cause="ریشه")

    def action(self, nc, due_in=5):
        return services.add_action(
            nc, actor=self.rag_lead, title="اقدام", assignee=self.worker, due_on=timezone.localdate() + timedelta(days=due_in)
        )

    def finish(self, nc, action):
        for status in ("IN_PROGRESS", "DONE"):
            action = services.update_action(nc, action, actor=self.worker, changes={"status": status})
        return action

    def closed(self):
        nc = self.accepted()
        action = self.finish(nc, self.action(nc))
        services.verify_action(nc, action, actor=self.rag_lead)
        return services.close(nc, actor=self.rag_lead, effectiveness_note="اثربخش بود")


class GateTests(QualityReportBase):
    def test_the_export_is_for_view_reports_alone(self):
        self.assertEqual(self.api(self.reporter).get(reverse("reports-quality-export")).status_code, 403)
        self.assertEqual(self.api(self.rag_lead).get(reverse("reports-quality-export")).status_code, 403)  # leading a unit is not enough
        self.assertEqual(self.api().get(reverse("reports-quality-export")).status_code, 401)
        self.assertEqual(self.api(self.qm).get(reverse("reports-quality-export")).status_code, 200)
        self.assertEqual(self.api(self.ceo).get(reverse("reports-quality-export")).status_code, 200)


class EmptyTests(QualityReportBase):
    def test_with_nothing_recorded_every_figure_is_zero_and_no_rate_pretends_to_be_one(self):
        q = self.kpi()
        self.assertEqual(q["nonconformances"]["open"], 0)
        self.assertEqual(q["nonconformances"]["aging"], {"0_30": 0, "31_60": 0, "61_90": 0, "over_90": 0})
        self.assertEqual(q["nonconformances"]["time_to_close"]["count"], 0)
        self.assertIsNone(q["nonconformances"]["time_to_close"]["average_days"])
        self.assertEqual((q["actions"]["verified_in_window"], q["actions"]["on_time_rate"]), (0, None))
        self.assertEqual(q["risks"], {"live": 0, "levels": {"low": 0, "medium": 0, "high": 0, "critical": 0}, "review_overdue": 0, "without_owner": 0})
        self.assertEqual(q["scope_note"], "مواردی که شما حق دیدنشان را دارید")


class RecordTests(QualityReportBase):
    def test_open_records_by_status_severity_and_age(self):
        fresh = self.make(severity="CRITICAL")
        middle = self.make()  # MAJOR, the fixture's default
        old = self.accepted()
        rejected = self.make()
        services.reject(rejected, actor=self.rag_lead, reason="تکراری")
        NonConformance.objects.filter(pk=middle.pk).update(created_at=_ago(45))
        NonConformance.objects.filter(pk=old.pk).update(created_at=_ago(100))
        q = self.kpi()["nonconformances"]
        self.assertEqual(q["open"], 3)
        self.assertEqual(q["by_status"], {"OPEN": 2, "IN_PROGRESS": 1, "CLOSED": 0, "REJECTED": 1})
        self.assertEqual(q["open_by_severity"], {"MINOR": 0, "MAJOR": 2, "CRITICAL": 1})
        self.assertEqual(q["aging"], {"0_30": 1, "31_60": 1, "61_90": 0, "over_90": 1})
        self.assertEqual(q["reported_in_window"], 3)  # the 100-day-old one is outside the 90-day window
        self.assertEqual(fresh.status, "OPEN")

    def test_the_aging_buckets_meet_at_their_edges_without_overlap(self):
        # Half a day either side of each edge (a whole number of days sits exactly on it and cannot tell
        # a shifted edge from the right one).
        for days in (29.5, 30.5, 59.5, 60.5, 89.5, 90.5):
            nc = self.make()
            NonConformance.objects.filter(pk=nc.pk).update(created_at=_ago(days))
        self.assertEqual(self.kpi()["nonconformances"]["aging"], {"0_30": 1, "31_60": 2, "61_90": 2, "over_90": 1})

    def test_time_to_close_counts_from_reported_to_closed_within_the_window(self):
        recent = self.closed()
        NonConformance.objects.filter(pk=recent.pk).update(created_at=_ago(10))
        long_ago = self.closed()
        NonConformance.objects.filter(pk=long_ago.pk).update(created_at=_ago(60), closed_at=_ago(40))
        week = self.kpi(days=7)["nonconformances"]["time_to_close"]
        self.assertEqual(week["count"], 1)
        self.assertAlmostEqual(week["average_days"], 10, delta=0.05)
        quarter = self.kpi(days=90)["nonconformances"]["time_to_close"]
        self.assertEqual((quarter["count"], quarter["longest_days"]), (2, 20.0))
        self.assertAlmostEqual(quarter["average_days"], 15, delta=0.05)


class ActionTests(QualityReportBase):
    def test_on_time_rate_over_the_actions_verified_in_the_window(self):
        nc = self.accepted()
        on_time = self.finish(nc, self.action(nc, due_in=5))
        late = self.finish(nc, self.action(nc, due_in=5))
        CorrectiveAction.objects.filter(pk=late.pk).update(completed_at=timezone.now() + timedelta(days=7))  # finished after the deadline
        for action in (on_time, late):
            services.verify_action(nc, CorrectiveAction.objects.get(pk=action.pk), actor=self.rag_lead)
        q = self.kpi()["actions"]
        self.assertEqual((q["verified_in_window"], q["on_time"], q["on_time_rate"]), (2, 1, 50.0))
        CorrectiveAction.objects.filter(pk=late.pk).update(verified_at=_ago(200))
        q = self.kpi()["actions"]
        self.assertEqual((q["verified_in_window"], q["on_time"], q["on_time_rate"]), (1, 1, 100.0))

    def test_open_and_overdue_actions_are_only_those_still_to_do_on_a_record_being_worked(self):
        nc = self.accepted()
        overdue = self.action(nc)
        CorrectiveAction.objects.filter(pk=overdue.pk).update(due_on=timezone.localdate() - timedelta(days=2))
        self.action(nc)  # open, not late
        done = self.finish(nc, self.action(nc))  # waiting on a verifier: not the assignee's to do
        q = self.kpi()["actions"]
        self.assertEqual((q["open"], q["overdue"]), (2, 1))
        services.cancel_action(nc, CorrectiveAction.objects.get(pk=overdue.pk), actor=self.rag_lead, reason="x")
        self.assertEqual((self.kpi()["actions"]["open"], self.kpi()["actions"]["overdue"]), (1, 0))
        self.assertEqual(done.status, "DONE")


class AuditFigureTests(QualityReportBase):
    def test_audits_completed_planned_late_running_and_findings(self):
        self.make()  # an ordinary report: not a finding
        done = self.running()
        self.raise_finding(done)
        services.complete_audit(done, actor=self.auditor, summary="خلاصه")
        late = self.plan()
        InternalAudit.objects.filter(pk=late.pk).update(planned_on=timezone.localdate() - timedelta(days=3))
        self.plan()  # planned, on time
        self.running()  # in progress
        q = self.kpi()["audits"]
        self.assertEqual(q, {"completed_in_window": 1, "planned": 2, "late": 1, "in_progress": 1, "findings_in_window": 1})


class RiskFigureTests(QualityReportBase):
    def test_risk_levels_reviews_and_owners_over_the_risks_still_on_the_register(self):
        self.make_risk(likelihood=3, impact=4, owner=self.owner.pk)  # high
        self.make_risk(likelihood=5, impact=5)  # critical, no owner
        overdue = self.make_risk(likelihood=1, impact=1, owner=self.owner.pk)  # low
        RiskItem.objects.filter(pk=overdue.pk).update(review_on=timezone.localdate() - timedelta(days=1))
        gone = self.make_risk(likelihood=5, impact=4)
        self.patch_risk(gone, status="CLOSED")
        RiskItem.objects.filter(pk=gone.pk).update(review_on=timezone.localdate() - timedelta(days=9))
        q = self.kpi()["risks"]
        self.assertEqual(q, {"live": 3, "levels": {"low": 1, "medium": 0, "high": 1, "critical": 1}, "review_overdue": 1, "without_owner": 1})


class ExportTests(QualityReportBase):
    def test_one_row_per_record_newest_first_with_the_derived_counts(self):
        older = self.accepted()
        self.action(older)
        overdue = self.action(older)
        CorrectiveAction.objects.filter(pk=overdue.pk).update(due_on=timezone.localdate() - timedelta(days=1))
        audit = self.running()
        finding = self.raise_finding(audit)
        rows = _rows(self.api(self.qm).get(reverse("reports-quality-export")))
        header, body = rows[0], rows[1:]
        self.assertEqual(header[:5], ["کد", "عنوان", "منبع", "شدت", "وضعیت"])
        self.assertEqual([r[0] for r in body], [finding.code, older.code])
        by_code = {r[0]: dict(zip(header, r)) for r in body}
        self.assertEqual(by_code[finding.code]["ممیزی"], audit.code)
        self.assertEqual(by_code[finding.code]["منبع"], "ممیزی")
        self.assertEqual((by_code[older.code]["تعداد اقدام"], by_code[older.code]["اقدام دیرکرد"]), ("2", "1"))
        self.assertEqual(by_code[older.code]["ریشهٔ مشکل"], "ریشه")

    def test_text_a_spreadsheet_would_run_is_defused(self):
        self.make(title="=HYPERLINK(1)", description="+cmd")
        body = _rows(self.api(self.qm).get(reverse("reports-quality-export")))[1]
        self.assertEqual(body[1], "'=HYPERLINK(1)")

    def test_the_filters_and_an_unknown_value(self):
        open_one = self.make()
        rejected = self.make(severity="CRITICAL")
        services.reject(rejected, actor=self.rag_lead, reason="x")
        codes = lambda **p: [r[0] for r in _rows(self.api(self.qm).get(reverse("reports-quality-export"), p))[1:]]
        self.assertEqual(codes(status="REJECTED"), [rejected.code])
        self.assertEqual(codes(severity="MAJOR"), [open_one.code])
        self.assertEqual(codes(source="AUDIT"), [])
        self.assertEqual(codes(status="bogus"), [])
        self.assertEqual(len(codes()), 2)
