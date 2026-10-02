from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from apps.core.constants import DocumentCategory, DocumentGroup
from apps.documents import services as document_services
from apps.documents import test_support
from apps.notifications.models import Notification, NotificationKind
from apps.organization import tree
from apps.organization.access import OrgAccess
from apps.organization.models import Delegation

from . import services
from .access import can_manage
from .models import NcSeverity, NcSource, NcStatus, NonConformance, QualityEvent, QualityEventKind
from .test_support import QualityBase, person  # noqa: F401


class AuthorityTableTests(QualityBase):
    """The manager rule and the visibility rule, for every kind of person against one record at RAG —
    the table the plan promised, so the rule cannot drift between the places that ask it."""

    def people(self):
        return {
            "reporter": self.reporter, "rag_lead": self.rag_lead, "ai_lead": self.ai_lead, "dev_lead": self.dev_lead,
            "qm": self.qm, "ceo": self.ceo, "outsider": self.outsider, "developer": self.developer,
        }

    def test_who_manages_a_record_at_rag(self):
        expected = {
            "reporter": False, "rag_lead": True, "ai_lead": True, "dev_lead": False,
            "qm": True, "ceo": True, "outsider": False, "developer": False,
        }
        for name, user in self.people().items():
            with self.subTest(name):
                self.assertEqual(can_manage(OrgAccess(user), self.org.rag), expected[name])

    def test_who_can_see_a_record_at_rag(self):
        nc = self.make()
        expected = {
            "reporter": True, "rag_lead": True, "ai_lead": True, "dev_lead": False,
            "qm": True, "ceo": True, "outsider": False, "developer": False,
        }
        for name, user in self.people().items():
            with self.subTest(name):
                self.assertEqual(self.api(user).get(self.url("nonconformance-detail", nc)).status_code, 200 if expected[name] else 404)
                listed = [r["id"] for r in self.api(user).get(reverse("nonconformance-list")).data["results"]]
                self.assertEqual(nc.pk in listed, expected[name])

    def test_an_invisible_record_is_a_404_everywhere_never_a_403(self):
        nc = self.make()
        client = self.api(self.outsider)
        for name in ("nonconformance-detail", "nonconformance-activity"):
            self.assertEqual(client.get(self.url(name, nc)).status_code, 404, name)
        for action, payload in (("accept", {"root_cause": "x"}), ("reject", {"reason": "x"}), ("reopen", {"reason": "x"})):
            response = client.post(self.url(f"nonconformance-{action}", nc), payload, format="json")
            self.assertEqual(response.status_code, 404, action)
        self.assertEqual(client.patch(self.url("nonconformance-detail", nc), {"title": "x"}, format="json").status_code, 404)

    def test_a_delegate_counts_as_a_lead_only_while_the_window_is_open(self):
        nc = self.make()
        today = timezone.localdate()
        window = Delegation.objects.create(node=self.org.ai, delegate=self.outsider, starts_on=today, ends_on=today + timedelta(days=2))
        self.assertEqual(self.api(self.outsider).get(self.url("nonconformance-detail", nc)).status_code, 200)
        self.assertTrue(self.api(self.outsider).get(self.url("nonconformance-detail", nc)).data["can_triage"])
        Delegation.objects.filter(pk=window.pk).update(starts_on=today - timedelta(days=9), ends_on=today - timedelta(days=1))
        self.assertEqual(self.api(self.outsider).get(self.url("nonconformance-detail", nc)).status_code, 404)

    def test_the_reporter_keeps_reading_their_own_report_after_leaving_the_unit(self):
        nc = self.make()
        from apps.organization.models import Membership

        Membership.objects.filter(user=self.reporter).delete()
        self.assertEqual(self.api(self.reporter).get(self.url("nonconformance-detail", nc)).status_code, 200)


class ReportTests(QualityBase):
    def test_anyone_may_report_even_against_a_unit_they_have_nothing_to_do_with(self):
        nc = self.make(self.outsider, owner_node=self.org.llm.pk)
        self.assertEqual((nc.status, nc.reported_by_id), (NcStatus.OPEN, self.outsider.pk))

    def test_the_developer_account_cannot_report(self):
        response = self.api(self.developer).post(reverse("nonconformance-list"), self.body(), format="json")
        self.assertEqual(response.status_code, 403)

    def test_anonymous_is_refused(self):
        self.assertEqual(self.api().post(reverse("nonconformance-list"), self.body(), format="json").status_code, 401)
        self.assertEqual(self.api().get(reverse("nonconformance-list")).status_code, 401)

    def test_the_code_comes_from_the_id(self):
        nc = self.make()
        self.assertEqual(nc.code, f"NC-{nc.pk:04d}")
        data = self.api(self.reporter).get(self.url("nonconformance-detail", nc)).data
        self.assertEqual((data["code"], data["status"], data["owner_node_name"]), (nc.code, "OPEN", "RAG"))

    def test_title_and_description_are_required_and_the_title_is_normalised(self):
        for bad in ({"title": "  "}, {"description": ""}):
            self.assertEqual(
                self.api(self.reporter).post(reverse("nonconformance-list"), self.body(**bad), format="json").status_code, 400, bad
            )
        self.assertEqual(self.make(title="مشكل   بزرگ").title, "مشکل بزرگ")  # Arabic kaf folded, spaces collapsed

    def test_the_detection_date_is_never_in_the_future(self):
        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        response = self.api(self.reporter).post(reverse("nonconformance-list"), self.body(detected_on=tomorrow), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.make(detected_on=timezone.localdate().isoformat()).detected_on, timezone.localdate())

    def test_an_archived_node_takes_no_new_reports(self):
        tree.archive_node(self.org.rag)
        response = self.api(self.reporter).post(reverse("nonconformance-list"), self.body(), format="json")
        self.assertEqual((response.status_code, response.data["code"]), (409, "node_archived"))
        self.assertEqual(NonConformance.objects.count(), 0)

    def test_a_related_document_is_linked_and_shown(self):
        document = document_services.create_document(
            user=self.rag_lead, category=DocumentCategory.INSIDE, title="روش کنترل", group=DocumentGroup.PROCEDURE, owner_node=self.org.rag
        )
        nc = self.make(related_document=document.pk)
        data = self.api(self.reporter).get(self.url("nonconformance-detail", nc)).data
        self.assertEqual((data["related_document_code"], data["related_document_title"]), (document.full_code, "روش کنترل"))

    def test_reporting_is_recorded_with_a_snapshot_of_who(self):
        nc = self.make()
        event = QualityEvent.objects.get(nc=nc)
        self.assertEqual((event.kind, event.actor_name, event.actor_title, event.to_status), (QualityEventKind.NC_REPORTED, self.reporter.full_name, self.reporter.title, "OPEN"))

    def test_the_leads_of_the_node_chain_are_told_once_and_the_reporter_is_not(self):
        nc = self.make()
        told = set(Notification.objects.filter(kind=NotificationKind.NC_REPORTED).values_list("recipient_id", flat=True))
        self.assertEqual(told, {self.rag_lead.pk, self.ai_lead.pk})  # not the sibling unit's lead, not the reporter
        self.assertTrue(all(n.url == f"/quality/{nc.pk}" for n in Notification.objects.filter(kind=NotificationKind.NC_REPORTED)))

    def test_a_lead_reporting_in_their_own_unit_is_not_told_about_it(self):
        self.make(self.rag_lead)
        told = set(Notification.objects.filter(kind=NotificationKind.NC_REPORTED).values_list("recipient_id", flat=True))
        self.assertEqual(told, {self.ai_lead.pk})

    def test_with_nobody_leading_the_ceo_is_told(self):
        lone = tree.create_node(kind="SECTION", name="بخش بی‌مسئول", parent=self.org.dev)  # dev's lead is above it, so use a bare node
        from apps.organization.models import Membership

        Membership.objects.filter(is_lead=True).delete()
        self.make(owner_node=lone.pk)
        told = set(Notification.objects.filter(kind=NotificationKind.NC_REPORTED).values_list("recipient_id", flat=True))
        self.assertEqual(told, {self.ceo.pk})


class EditTests(QualityBase):
    def patch(self, user, nc, **changes):
        return self.api(user).patch(self.url("nonconformance-detail", nc), changes, format="json")

    def test_the_reporter_may_correct_their_own_open_report(self):
        nc = self.make()
        self.assertEqual(self.patch(self.reporter, nc, title="عنوان بهتر").status_code, 200)
        nc.refresh_from_db()
        self.assertEqual(nc.title, "عنوان بهتر")
        event = QualityEvent.objects.filter(kind=QualityEventKind.NC_EDITED).get()
        self.assertEqual(event.note, "عنوان")

    def test_once_accepted_the_reporter_can_no_longer_edit_but_a_manager_can(self):
        nc = self.make()
        services.accept(nc, actor=self.rag_lead, root_cause="دلیل")
        self.assertEqual(self.patch(self.reporter, nc, title="x").status_code, 403)
        self.assertEqual(self.patch(self.rag_lead, nc, severity=NcSeverity.CRITICAL).status_code, 200)

    def test_someone_else_cannot_edit_a_report_they_can_see(self):
        nc = self.make()
        other = person()
        test_support.lead_of(other, self.org.llm)  # leads the sibling بخش: cannot even see it
        self.assertEqual(self.patch(other, nc, title="x").status_code, 404)

    def test_a_rejected_record_is_read_only_until_reopened(self):
        nc = self.make()
        services.reject(nc, actor=self.rag_lead, reason="تکراری")
        response = self.patch(self.rag_lead, nc, title="x")
        self.assertEqual((response.status_code, response.data["code"]), (409, "wrong_status"))

    def test_an_edit_that_changes_nothing_writes_no_line(self):
        nc = self.make()
        self.patch(self.reporter, nc, title=nc.title, severity=nc.severity)
        self.assertEqual(self.kinds(nc), [QualityEventKind.NC_REPORTED])

    def test_the_note_lists_every_field_that_changed(self):
        nc = self.make()
        self.patch(self.reporter, nc, title="جدید", severity=NcSeverity.CRITICAL)
        self.assertEqual(QualityEvent.objects.filter(kind=QualityEventKind.NC_EDITED).get().note, "عنوان، شدت")

    def test_a_manager_hands_it_to_another_unit_only_if_they_lead_there_too(self):
        nc = self.make()
        services.accept(nc, actor=self.rag_lead, root_cause="دلیل")
        refused = self.patch(self.rag_lead, nc, owner_node=self.org.dev.pk)
        self.assertEqual(refused.status_code, 403)
        allowed = self.patch(self.ai_lead, nc, owner_node=self.org.llm.pk)  # leads هوش مصنوعی: both ends
        self.assertEqual(allowed.status_code, 200)

    def test_an_archived_target_node_is_refused(self):
        nc = self.make()
        tree.archive_node(self.org.llm)
        response = self.patch(self.reporter, nc, owner_node=self.org.llm.pk)
        self.assertEqual((response.status_code, response.data["code"]), (409, "node_archived"))


class TriageTests(QualityBase):
    def post(self, user, nc, action, **payload):
        return self.api(user).post(self.url(f"nonconformance-{action}", nc), payload, format="json")

    def test_a_manager_accepts_with_a_root_cause(self):
        nc = self.make()
        response = self.post(self.rag_lead, nc, "accept", root_cause="کنترل ورودی انجام نشد", severity="CRITICAL")
        self.assertEqual(response.status_code, 200, response.data)
        nc.refresh_from_db()
        self.assertEqual((nc.status, nc.root_cause, nc.severity), (NcStatus.IN_PROGRESS, "کنترل ورودی انجام نشد", "CRITICAL"))
        self.assertIsNotNone(nc.accepted_at)
        event = QualityEvent.objects.get(kind=QualityEventKind.NC_ACCEPTED)
        self.assertEqual((event.from_status, event.to_status, event.actor_name), ("OPEN", "IN_PROGRESS", self.rag_lead.full_name))

    def test_accepting_without_a_root_cause_is_refused_and_leaves_no_line(self):
        nc = self.make()
        self.assertEqual(self.post(self.rag_lead, nc, "accept", root_cause="  ").status_code, 400)
        self.assertEqual(self.kinds(nc), [QualityEventKind.NC_REPORTED])
        nc.refresh_from_db()
        self.assertEqual(nc.status, NcStatus.OPEN)

    def test_only_a_manager_triages(self):
        nc = self.make()
        for who in (self.reporter,):  # can see it, may not triage it
            self.assertEqual(self.post(who, nc, "accept", root_cause="x").status_code, 403)
            self.assertEqual(self.post(who, nc, "reject", reason="x").status_code, 403)
        self.assertEqual(self.kinds(nc), [QualityEventKind.NC_REPORTED])

    def test_a_refused_transition_leaves_no_line_and_no_change(self):
        nc = self.make()
        services.accept(nc, actor=self.rag_lead, root_cause="دلیل")
        before = self.kinds(nc)
        response = self.post(self.rag_lead, nc, "accept", root_cause="دوباره")
        self.assertEqual((response.status_code, response.data["code"]), (409, "wrong_status"))
        self.assertEqual(self.post(self.rag_lead, nc, "reject", reason="x").status_code, 409)
        self.assertEqual(self.kinds(nc), before)

    def test_reject_needs_a_reason_and_keeps_it(self):
        nc = self.make()
        self.assertEqual(self.post(self.ai_lead, nc, "reject", reason="").status_code, 400)
        self.assertEqual(self.post(self.ai_lead, nc, "reject", reason="تکراری است").status_code, 200)
        nc.refresh_from_db()
        self.assertEqual((nc.status, nc.rejection_reason), (NcStatus.REJECTED, "تکراری است"))
        self.assertEqual(QualityEvent.objects.get(kind=QualityEventKind.NC_REJECTED).note, "تکراری است")

    def test_a_rejected_report_goes_back_to_triage_not_straight_to_in_progress(self):
        nc = self.make()
        services.reject(nc, actor=self.rag_lead, reason="x")
        self.assertEqual(self.post(self.rag_lead, nc, "reopen", reason="شواهد جدید").status_code, 200)
        nc.refresh_from_db()
        self.assertEqual((nc.status, nc.rejection_reason), (NcStatus.OPEN, ""))
        self.assertEqual(self.post(self.rag_lead, nc, "reopen", reason="x").status_code, 409)  # an OPEN record has nothing to reopen

    def test_the_reporter_is_told_unless_they_did_it_themselves(self):
        nc = self.make()
        services.accept(nc, actor=self.rag_lead, root_cause="دلیل")
        note = Notification.objects.get(kind=NotificationKind.NC_ACCEPTED)
        self.assertEqual((note.recipient_id, note.url), (self.reporter.pk, f"/quality/{nc.pk}"))
        own = self.make(self.rag_lead)
        services.reject(own, actor=self.rag_lead, reason="x")
        self.assertFalse(Notification.objects.filter(kind=NotificationKind.NC_REJECTED, recipient=self.rag_lead).exists())

    def test_the_detail_offers_exactly_the_buttons_the_server_allows(self):
        nc = self.make()
        as_lead = self.api(self.rag_lead).get(self.url("nonconformance-detail", nc)).data
        as_reporter = self.api(self.reporter).get(self.url("nonconformance-detail", nc)).data
        self.assertEqual((as_lead["can_triage"], as_lead["can_edit"], as_lead["can_reopen"]), (True, True, False))
        self.assertEqual((as_reporter["can_triage"], as_reporter["can_edit"], as_reporter["can_reopen"]), (False, True, False))
        services.accept(nc, actor=self.rag_lead, root_cause="دلیل")
        as_reporter = self.api(self.reporter).get(self.url("nonconformance-detail", nc)).data
        self.assertEqual((as_reporter["can_triage"], as_reporter["can_edit"]), (False, False))


class ListAndFeedTests(QualityBase):
    def test_filters(self):
        a = self.make(title="الف", severity=NcSeverity.MINOR)
        b = self.make(title="ب", severity=NcSeverity.CRITICAL, source=NcSource.COMPLAINT, owner_node=self.org.llm.pk)
        services.accept(a, actor=self.rag_lead, root_cause="x")
        client = self.api(self.qm)

        def ids(**params):
            return sorted(r["id"] for r in client.get(reverse("nonconformance-list"), params).data["results"])

        self.assertEqual(ids(), sorted([a.pk, b.pk]))
        self.assertEqual(ids(status="IN_PROGRESS"), [a.pk])
        self.assertEqual(ids(severity="CRITICAL"), [b.pk])
        self.assertEqual(ids(source="COMPLAINT"), [b.pk])
        self.assertEqual(ids(status="nonsense"), [])  # an unknown value matches nothing, never everything
        self.assertEqual(ids(node=self.org.rag.pk), [a.pk])
        self.assertEqual(ids(node=self.org.ai.pk), sorted([a.pk, b.pk]))  # a node includes everything beneath it
        self.assertEqual(ids(node="x"), [])
        self.assertEqual(ids(mine="reported"), [])  # the qm reported neither

    def test_search_by_text_and_by_code(self):
        a = self.make(title="قطعهٔ معیوب")
        self.make(title="نشت روغن")
        client = self.api(self.qm)
        search = lambda q: [r["id"] for r in client.get(reverse("nonconformance-list"), {"q": q}).data["results"]]
        self.assertEqual(search("معیوب"), [a.pk])
        self.assertEqual(search(a.code), [a.pk])
        self.assertEqual(search(str(a.pk)), [a.pk])
        self.assertEqual(search("nc-" + str(a.pk).zfill(4)), [a.pk])

    def test_mine_reported(self):
        mine = self.make(self.reporter)
        self.make(self.outsider)
        rows = self.api(self.reporter).get(reverse("nonconformance-list"), {"mine": "reported"}).data["results"]
        self.assertEqual([r["id"] for r in rows], [mine.pk])

    def test_the_feed_is_per_record_and_across_records_and_scoped(self):
        a = self.make()
        b = self.make(self.outsider, owner_node=self.org.dev.pk)  # a record the reporter may not read
        services.accept(a, actor=self.rag_lead, root_cause="x")
        per_record = self.api(self.reporter).get(self.url("nonconformance-activity", a)).data["results"]
        self.assertEqual([e["kind"] for e in per_record], ["nc_accepted", "nc_reported"])  # newest first
        self.assertEqual(per_record[0]["nc_code"], a.code)
        everything = self.api(self.reporter).get(reverse("quality-activity")).data["results"]
        self.assertEqual({e["nc"] for e in everything}, {a.pk})  # never b's lines
        self.assertEqual(self.api(self.reporter).get(reverse("quality-activity"), {"nc": b.pk}).data["count"], 0)
        self.assertEqual(self.api(self.reporter).get(self.url("nonconformance-activity", b)).status_code, 404)
        only_accepted = self.api(self.reporter).get(reverse("quality-activity"), {"kind": "nc_accepted"}).data["results"]
        self.assertEqual([e["kind"] for e in only_accepted], ["nc_accepted"])
        self.assertEqual(only_accepted[0]["to_status_label"], NcStatus.IN_PROGRESS.label)

    def test_the_closed_check_constraint_holds_in_the_database(self):
        from django.db import IntegrityError, transaction

        nc = self.make()
        with self.assertRaises(IntegrityError), transaction.atomic():
            NonConformance.objects.filter(pk=nc.pk).update(status=NcStatus.CLOSED)  # no closed_at

    def test_a_person_who_reported_cannot_be_deleted_and_the_answer_says_why(self):
        self.make(self.reporter)
        ceo = self.api(self.ceo)
        response = ceo.delete(reverse("personnel-detail", args=[self.reporter.pk]))
        self.assertIn(response.data["code"], {"user_has_quality_records", "user_has_memberships"})
        lone = person()
        self.make(lone)
        response = ceo.delete(reverse("personnel-detail", args=[lone.pk]))
        self.assertEqual((response.status_code, response.data["code"]), (409, "user_has_quality_records"))
