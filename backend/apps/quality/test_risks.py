"""The risk register (Phase 18, slice 7): who may create and edit, who may read, the derived score and
its bands, the permissive status, the history, the heat map's numbers and the review reminders. Risks
live in the بخش RAG (`test_support.RiskBase`): its مسئول manages them, the مسئول of the unit above does
too, a sibling unit's does not, and a person merely *named* as owner can read but not change."""
from datetime import timedelta

from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.notifications import tasks as notification_tasks
from apps.notifications.models import Notification, NotificationKind
from apps.organization import tree
from apps.organization.models import Membership

from . import services
from .models import QualityEventKind, RiskItem, RiskStatus
from .queries import RISK_LEVELS, risk_level
from .test_support import RiskBase, person


def _told(kind):
    return list(Notification.objects.filter(kind=kind).order_by("id").values_list("recipient_id", flat=True))


def _soon(days=1):
    return timezone.localdate() + timedelta(days=days)


class CreateTests(RiskBase):
    def test_who_may_create_one(self):
        for who in (self.qm, self.ceo, self.rag_lead, self.ai_lead):  # manage_quality, or a lead of the node or above it
            self.assertEqual(self.api(who).post(reverse("risk-list"), self.risk_body(), format="json").status_code, 201, who.full_name)
        RiskItem.objects.all().delete()
        for who in (self.dev_lead, self.reporter, self.outsider, self.owner, self.developer):
            self.assertEqual(self.api(who).post(reverse("risk-list"), self.risk_body(), format="json").status_code, 403, who.full_name)
        self.assertEqual(self.api().post(reverse("risk-list"), self.risk_body(), format="json").status_code, 401)
        self.assertEqual(RiskItem.objects.count(), 0)

    def test_the_new_risk_is_identified_and_carries_its_derived_numbers(self):
        risk = self.make_risk()
        data = self.api(self.rag_lead).get(self.risk_url(risk)).data
        self.assertEqual(data["code"], f"RK-{risk.pk:04d}")
        self.assertEqual((data["status"], data["score"], data["level"], data["level_label"]), ("IDENTIFIED", 12, "high", "زیاد"))
        self.assertEqual((data["owner"], data["owner_name"], data["created_by_name"], data["can_edit"]), (None, None, self.rag_lead.full_name, True))
        self.assertEqual((data["owner_node_name"], data["review_overdue"], data["mitigation_plan"]), ("RAG", False, ""))
        self.assertFalse(hasattr(RiskItem, "score"))  # a number computed from two columns, never a column

    def test_each_scale_must_be_a_whole_number_from_one_to_five(self):
        for field in ("likelihood", "impact"):
            for bad in (0, 6, -1, 2.5, "x", None):
                response = self.api(self.qm).post(reverse("risk-list"), self.risk_body(**{field: bad}), format="json")
                self.assertEqual(response.status_code, 400, (field, bad))
                self.assertIn(field, response.data)
        self.assertEqual(RiskItem.objects.count(), 0)

    def test_the_text_fields(self):
        for bad in ({"title": "  "}, {"title": ""}, {"description": ""}, {"description": "   "}):
            self.assertEqual(self.api(self.qm).post(reverse("risk-list"), self.risk_body(**bad), format="json").status_code, 400, bad)
        risk = self.make_risk(title="خطر   بزرگ", mitigation_plan="  دو تامین‌کننده  ")
        self.assertEqual((risk.title, risk.mitigation_plan), ("خطر بزرگ", "دو تامین‌کننده"))

    def test_an_archived_node_takes_no_risk(self):
        tree.archive_node(self.org.llm)
        response = self.api(self.qm).post(reverse("risk-list"), self.risk_body(owner_node=self.org.llm.pk), format="json")
        self.assertEqual((response.status_code, response.data["code"]), (409, "node_archived"))

    def test_a_named_owner_must_be_able_to_act(self):
        for bad in (person(is_active=False), self.developer):
            response = self.api(self.qm).post(reverse("risk-list"), self.risk_body(owner=bad.pk), format="json")
            self.assertEqual((response.status_code, response.data["code"]), (409, "owner_not_eligible"))
        self.assertEqual(self.make_risk(owner=self.owner.pk).owner_id, self.owner.pk)

    def test_a_review_date_in_the_past_is_refused_but_today_is_fine(self):
        response = self.api(self.qm).post(reverse("risk-list"), self.risk_body(review_on=_soon(-1).isoformat()), format="json")
        self.assertEqual((response.status_code, response.data["code"]), (409, "review_in_past"))
        self.assertEqual(self.make_risk(review_on=timezone.localdate().isoformat()).review_on, timezone.localdate())

    def test_creation_is_recorded_and_the_owner_is_told_unless_they_did_it(self):
        risk = self.make_risk(owner=self.owner.pk)
        event = risk.events.get()
        self.assertEqual((event.kind, event.actor_name, event.to_status, event.note), (QualityEventKind.RISK_CREATED, self.rag_lead.full_name, "IDENTIFIED", "۳×۴"))
        note = Notification.objects.get(kind=NotificationKind.RISK_ASSIGNED)
        self.assertEqual((note.recipient_id, note.url), (self.owner.pk, f"/quality/risks/{risk.pk}"))
        self.make_risk(user=self.qm, owner=self.qm.pk)
        self.assertEqual(_told(NotificationKind.RISK_ASSIGNED), [self.owner.pk])  # the creator-owner is not told

    def test_a_refused_creation_leaves_no_trace(self):
        notifications = Notification.objects.count()
        self.api(self.dev_lead).post(reverse("risk-list"), self.risk_body(), format="json")
        self.api(self.qm).post(reverse("risk-list"), self.risk_body(likelihood=9, owner=self.owner.pk), format="json")
        self.api(self.qm).post(reverse("risk-list"), self.risk_body(review_on="2001-01-01", owner=self.owner.pk), format="json")
        self.assertEqual((RiskItem.objects.count(), Notification.objects.count()), (0, notifications))
        self.assertEqual(self.risk_kinds_all(), [])

    def risk_kinds_all(self):
        from .models import QualityEvent

        return list(QualityEvent.objects.filter(risk__isnull=False).values_list("kind", flat=True))

    def test_the_service_repeats_the_scale_rule_for_whoever_calls_it(self):
        for bad in (0, 6, True, 3.0, "3"):
            with self.assertRaises(ValidationError, msg=repr(bad)):
                services.create_risk(
                    actor=self.qm, title="x", description="y", owner_node=self.org.rag, likelihood=bad, impact=2
                )
        self.assertEqual(RiskItem.objects.count(), 0)

    def test_the_database_itself_refuses_a_scale_outside_one_to_five(self):
        risk = self.make_risk()
        for field in ("likelihood", "impact"):
            for bad in (0, 6):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    RiskItem.objects.filter(pk=risk.pk).update(**{field: bad})


class LevelTests(RiskBase):
    #: Likelihood × impact can only be one of these; each is in exactly one band. Written out by hand so the
    #: test is not a copy of the code under test.
    EXPECTED = {
        1: "low", 2: "low", 3: "low", 4: "low",
        5: "medium", 6: "medium", 8: "medium", 9: "medium",
        10: "high", 12: "high",
        15: "critical", 16: "critical", 20: "critical", 25: "critical",
    }

    def test_every_one_of_the_25_cells_has_the_right_level(self):
        for likelihood in range(1, 6):
            for impact in range(1, 6):
                risk = RiskItem.objects.create(
                    title=f"{likelihood}x{impact}", description="d", owner_node=self.org.rag, created_by=self.rag_lead,
                    likelihood=likelihood, impact=impact,
                )
                data = self.api(self.qm).get(self.risk_url(risk)).data
                self.assertEqual((data["score"], data["level"]), (likelihood * impact, self.EXPECTED[likelihood * impact]), f"{likelihood}×{impact}")

    def test_the_bands_cover_one_to_twenty_five_with_no_gap_and_no_overlap(self):
        self.assertEqual([(key, low, high) for key, _, low, high in RISK_LEVELS], [("low", 1, 4), ("medium", 5, 9), ("high", 10, 14), ("critical", 15, 25)])
        for score in range(1, 26):
            self.assertEqual(sum(low <= score <= high for _, _, low, high in RISK_LEVELS), 1, score)
        for bad in (0, 26, -3):
            with self.assertRaises(ValueError):
                risk_level(bad)

    def test_the_level_filter_matches_each_band_and_nothing_for_an_unknown_one(self):
        made = {
            (1, 1): None, (2, 3): None, (3, 4): None, (5, 5): None,  # low, medium, high, critical
        }
        for (likelihood, impact) in made:
            made[(likelihood, impact)] = RiskItem.objects.create(
                title="t", description="d", owner_node=self.org.rag, created_by=self.rag_lead, likelihood=likelihood, impact=impact
            ).pk
        ids = lambda level: {r["id"] for r in self.api(self.qm).get(reverse("risk-list"), {"level": level}).data["results"]}
        self.assertEqual(ids("low"), {made[(1, 1)]})
        self.assertEqual(ids("medium"), {made[(2, 3)]})
        self.assertEqual(ids("high"), {made[(3, 4)]})
        self.assertEqual(ids("critical"), {made[(5, 5)]})
        self.assertEqual(ids("bogus"), set())


class VisibilityTests(RiskBase):
    def setUp(self):
        super().setUp()
        self.risk = self.make_risk(owner=self.owner.pk)

    def see(self, user, name="risk-list"):
        return {row["id"] for row in self.api(user).get(reverse(name)).data["results"]}

    def test_who_reads_what(self):
        for reader in (self.qm, self.ceo, self.rag_lead, self.ai_lead, self.owner):  # creator + lead, above, named owner
            self.assertEqual(self.see(reader), {self.risk.pk}, reader.full_name)
        for nobody in (self.dev_lead, self.reporter, self.outsider, self.developer):
            self.assertEqual(self.see(nobody), set(), nobody.full_name)

    def test_the_creator_keeps_sight_after_leaving_the_unit(self):
        Membership.objects.filter(user=self.rag_lead).delete()
        self.assertEqual(self.see(self.rag_lead), {self.risk.pk})

    def test_a_risk_you_may_not_read_is_a_404_everywhere_never_a_403(self):
        for name in ("risk-detail", "risk-activity"):
            self.assertEqual(self.api(self.dev_lead).get(self.risk_url(self.risk, name)).status_code, 404, name)
        self.assertEqual(self.patch_risk(self.risk, self.dev_lead, title="x").status_code, 404)
        self.assertEqual(self.patch_risk(self.risk, self.reporter, title="x").status_code, 404)

    def test_the_matrix_counts_only_what_you_may_read(self):
        self.make_risk(user=self.qm, owner_node=self.org.dev.pk, likelihood=5, impact=5)  # in the sibling unit
        total = lambda user: self.api(user).get(reverse("risk-matrix")).data["total"]
        self.assertEqual((total(self.qm), total(self.rag_lead), total(self.dev_lead), total(self.outsider)), (2, 1, 1, 0))


class EditTests(RiskBase):
    def setUp(self):
        super().setUp()
        self.risk = self.make_risk(owner=self.owner.pk)
        Notification.objects.all().delete()

    def test_who_may_edit_one(self):
        for who in (self.qm, self.ceo, self.rag_lead, self.ai_lead):
            self.assertEqual(self.patch_risk(self.risk, who, title=f"عنوان {who.pk}").status_code, 200, who.full_name)
        # The named owner can read it — and that is all.
        response = self.patch_risk(self.risk, self.owner, title="x")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.api(self.owner).get(self.risk_url(self.risk)).data["can_edit"], False)

    def test_every_flag_agrees_with_the_endpoint(self):
        for viewer in (self.qm, self.ceo, self.rag_lead, self.ai_lead, self.owner):
            offered = self.api(viewer).get(self.risk_url(self.risk)).data["can_edit"]
            worked = self.patch_risk(self.risk, viewer, title=f"من {viewer.pk}").status_code == 200
            self.assertEqual(offered, worked, viewer.full_name)

    def test_the_status_moves_anywhere_and_each_move_is_recorded(self):
        path = ["CLOSED", "IDENTIFIED", "ACCEPTED", "MITIGATING", "IDENTIFIED"]
        for target in path:
            response = self.patch_risk(self.risk, status=target)
            self.assertEqual((response.status_code, response.data["status"]), (200, target), target)
        moves = list(self.risk.events.filter(kind=QualityEventKind.RISK_STATUS_CHANGED).order_by("id").values_list("from_status", "to_status"))
        self.assertEqual(moves, list(zip(["IDENTIFIED", *path[:-1]], path)))

    def test_a_closed_risk_is_still_editable(self):
        # Permissive on purpose (the plan): there is no read-only state to get stuck in.
        self.patch_risk(self.risk, status="CLOSED")
        self.assertEqual(self.patch_risk(self.risk, mitigation_plan="بازنگری پس از بستن").status_code, 200)

    def test_an_invalid_status_is_refused(self):
        self.assertEqual(self.patch_risk(self.risk, status="NOPE").status_code, 400)
        with self.assertRaises(ValidationError):
            services.edit_risk(self.risk, actor=self.qm, changes={"status": "NOPE"})

    def test_a_reassessment_reads_before_arrow_after_and_one_line_covers_both_scales(self):
        self.patch_risk(self.risk, likelihood=4)
        self.assertEqual(self.risk.events.get(kind=QualityEventKind.RISK_ASSESSED).note, "۳×۴ ← ۴×۴")
        self.patch_risk(self.risk, likelihood=2, impact=5)
        notes = list(self.risk.events.filter(kind=QualityEventKind.RISK_ASSESSED).order_by("id").values_list("note", flat=True))
        self.assertEqual(notes, ["۳×۴ ← ۴×۴", "۴×۴ ← ۲×۵"])
        self.assertEqual(self.api(self.qm).get(self.risk_url(self.risk)).data["score"], 10)

    def test_the_scales_are_checked_on_edit_too(self):
        for body in ({"likelihood": 0}, {"impact": 6}):
            self.assertEqual(self.patch_risk(self.risk, **body).status_code, 400, body)
        with self.assertRaises(ValidationError):
            services.edit_risk(self.risk, actor=self.qm, changes={"likelihood": 9})

    def test_the_plain_fields_are_named_in_one_line(self):
        self.patch_risk(self.risk, title="عنوان تازه", mitigation_plan="برنامه", review_on=_soon(30).isoformat())
        event = self.risk.events.get(kind=QualityEventKind.RISK_EDITED)
        self.assertEqual(event.note, "عنوان، برنامهٔ کاهش، تاریخ بازنگری")

    def test_one_patch_with_everything_writes_three_lines_in_order(self):
        self.patch_risk(self.risk, title="تازه", impact=2, status="MITIGATING")
        self.assertEqual(
            self.risk_kinds(self.risk),
            [QualityEventKind.RISK_CREATED, QualityEventKind.RISK_EDITED, QualityEventKind.RISK_ASSESSED, QualityEventKind.RISK_STATUS_CHANGED],
        )

    def test_changing_nothing_records_nothing(self):
        before = self.risk_kinds(self.risk)
        self.patch_risk(self.risk, title=self.risk.title, likelihood=3, impact=4, status="IDENTIFIED", owner=self.owner.pk, mitigation_plan="", review_on=None)
        self.assertEqual(self.risk_kinds(self.risk), before)

    def test_naming_clearing_and_changing_the_owner(self):
        newcomer = person(name="مسئول جدید")
        self.assertEqual(self.patch_risk(self.risk, owner=newcomer.pk).data["owner_name"], "مسئول جدید")
        self.assertEqual(_told(NotificationKind.RISK_ASSIGNED), [newcomer.pk])
        self.assertEqual(self.risk.events.filter(kind=QualityEventKind.RISK_EDITED).last().note, "مسئول ریسک")
        cleared = self.patch_risk(self.risk, owner=None).data
        self.assertEqual((cleared["owner"], cleared["owner_name"]), (None, None))
        self.assertEqual(_told(NotificationKind.RISK_ASSIGNED), [newcomer.pk])  # clearing tells nobody
        response = self.patch_risk(self.risk, owner=self.developer.pk)
        self.assertEqual((response.status_code, response.data["code"]), (409, "owner_not_eligible"))

    def test_an_owner_who_is_the_editor_is_not_told(self):
        self.patch_risk(self.risk, self.rag_lead, owner=self.rag_lead.pk)
        self.assertEqual(_told(NotificationKind.RISK_ASSIGNED), [])

    def test_moving_it_to_another_node_needs_authority_there_too(self):
        # rag_lead leads RAG, not its sibling LLM: they may not hand the risk over.
        response = self.patch_risk(self.risk, self.rag_lead, owner_node=self.org.llm.pk)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.patch_risk(self.risk, self.ai_lead, owner_node=self.org.llm.pk).data["owner_node_name"], "LLM")
        self.assertEqual(self.patch_risk(self.risk, self.qm, owner_node=self.org.dev.pk).data["owner_node_name"], "توسعه")

    def test_an_archived_target_node_is_refused(self):
        tree.archive_node(self.org.llm)
        response = self.patch_risk(self.risk, self.ai_lead, owner_node=self.org.llm.pk)
        self.assertEqual((response.status_code, response.data["code"]), (409, "node_archived"))

    def test_the_review_date_is_checked_only_when_it_changes_and_can_be_cleared(self):
        RiskItem.objects.filter(pk=self.risk.pk).update(review_on=_soon(-3))
        self.assertEqual(self.patch_risk(self.risk, title="هنوز قابل ویرایش").status_code, 200)
        self.assertEqual(self.patch_risk(self.risk, review_on=_soon(-3).isoformat()).status_code, 200)  # unchanged
        response = self.patch_risk(self.risk, review_on=_soon(-1).isoformat())
        self.assertEqual((response.status_code, response.data["code"]), (409, "review_in_past"))
        self.assertIsNone(self.patch_risk(self.risk, review_on=None).data["review_on"])

    def test_the_overdue_flag_is_for_a_risk_still_on_the_register(self):
        RiskItem.objects.filter(pk=self.risk.pk).update(review_on=_soon(-2))
        self.assertTrue(self.api(self.qm).get(self.risk_url(self.risk)).data["review_overdue"])
        RiskItem.objects.filter(pk=self.risk.pk).update(status=RiskStatus.CLOSED)
        self.assertFalse(self.api(self.qm).get(self.risk_url(self.risk)).data["review_overdue"])

    def test_a_refused_edit_leaves_no_trace(self):
        before = self.risk_kinds(self.risk)
        self.patch_risk(self.risk, self.owner, title="x", status="CLOSED")
        self.patch_risk(self.risk, self.qm, title="x", impact=9)
        self.patch_risk(self.risk, self.qm, title="x", review_on="2001-01-01", owner=self.rag_lead.pk)
        self.risk.refresh_from_db()
        self.assertEqual((self.risk_kinds(self.risk), self.risk.title, Notification.objects.count()), (before, "قطع شدن سرویس مدل", 0))


class ListTests(RiskBase):
    def setUp(self):
        super().setUp()
        self.quiet = self.make_risk(title="خطر کم", likelihood=1, impact=2)  # score 2
        self.worst = self.make_risk(title="خطر بحرانی", likelihood=5, impact=5, owner=self.owner.pk)  # 25
        self.mid = self.make_risk(title="تاخیر تامین", description="فرایند خرید", likelihood=2, impact=3, review_on=_soon(2).isoformat())  # 6
        self.elsewhere = self.make_risk(user=self.qm, title="خطر توسعه", owner_node=self.org.dev.pk, likelihood=4, impact=4)  # 16

    def ids(self, user=None, **params):
        return [r["id"] for r in self.api(user or self.qm).get(reverse("risk-list"), params).data["results"]]

    def test_the_register_is_ordered_by_score_worst_first(self):
        self.assertEqual(self.ids(), [self.worst.pk, self.elsewhere.pk, self.mid.pk, self.quiet.pk])

    def test_ties_break_by_the_nearer_review_date_then_the_newer_risk(self):
        a = self.make_risk(title="الف", likelihood=3, impact=3)
        b = self.make_risk(title="ب", likelihood=3, impact=3, review_on=_soon(9).isoformat())
        c = self.make_risk(title="ج", likelihood=3, impact=3, review_on=_soon(4).isoformat())
        nine = [i for i in self.ids() if i in (a.pk, b.pk, c.pk)]
        self.assertEqual(nine, [c.pk, b.pk, a.pk])  # soonest review first, no review date last

    def test_the_filters(self):
        self.assertEqual(set(self.ids(status="IDENTIFIED")), {self.quiet.pk, self.worst.pk, self.mid.pk, self.elsewhere.pk})
        self.assertEqual(self.ids(status="CLOSED"), [])
        self.assertEqual(self.ids(status="bogus"), [])
        self.assertEqual(self.ids(likelihood=5), [self.worst.pk])
        self.assertEqual(self.ids(impact=3), [self.mid.pk])
        self.assertEqual(self.ids(likelihood=9), [])
        self.assertEqual(self.ids(likelihood="x"), [])
        self.assertEqual(set(self.ids(node=self.org.ai.pk)), {self.quiet.pk, self.worst.pk, self.mid.pk})  # that node and beneath
        self.assertEqual(self.ids(node=self.org.dev.pk), [self.elsewhere.pk])
        self.assertEqual(self.ids(node="x"), [])

    def test_mine(self):
        self.assertEqual(self.ids(self.owner, mine="owner"), [self.worst.pk])
        self.assertEqual(set(self.ids(self.rag_lead, mine="created")), {self.quiet.pk, self.worst.pk, self.mid.pk})
        self.assertEqual(self.ids(self.qm, mine="created"), [self.elsewhere.pk])
        self.assertEqual(set(self.ids(self.ai_lead, mine="manage")), {self.quiet.pk, self.worst.pk, self.mid.pk})
        self.assertEqual(self.ids(self.owner, mine="manage"), [])  # naming someone owner does not make them a manager
        self.assertEqual(len(self.ids(self.qm, mine="manage")), 4)

    def test_search_by_words_and_by_code_even_typed_with_persian_digits(self):
        self.assertEqual(self.ids(q="تاخیر"), [self.mid.pk])
        self.assertEqual(self.ids(q="فرایند خرید"), [self.mid.pk])  # the description too
        self.assertEqual(self.ids(q=self.worst.code), [self.worst.pk])
        self.assertEqual(self.ids(q=self.worst.code.lower()), [self.worst.pk])
        self.assertEqual(self.ids(q=str(self.worst.pk)), [self.worst.pk])
        persian = str(self.worst.pk).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
        self.assertEqual(self.ids(q=f"RK-{persian}"), [self.worst.pk])
        self.assertEqual(self.ids(q="چیزی که نیست"), [])

    def test_review_due_means_near_or_past_on_a_risk_still_on_the_register(self):
        near = self.make_risk(title="نزدیک", review_on=_soon(1).isoformat())
        past = self.make_risk(title="گذشته", review_on=timezone.localdate().isoformat())
        RiskItem.objects.filter(pk=past.pk).update(review_on=_soon(-5))
        far = self.make_risk(title="دور", review_on=_soon(90).isoformat())
        closed = self.make_risk(title="بسته", review_on=_soon(1).isoformat())
        self.patch_risk(closed, status="CLOSED")
        due = set(self.ids(review="due"))
        self.assertEqual(due, {near.pk, past.pk, self.mid.pk})
        self.assertNotIn(far.pk, due)
        self.assertNotIn(closed.pk, due)

    def test_the_list_costs_the_same_however_many_risks_there_are(self):
        def cost(user):
            with CaptureQueriesContext(connection) as queries:
                self.api(user).get(reverse("risk-list"))
            return len(queries)

        before = {user.pk: cost(user) for user in (self.qm, self.rag_lead)}
        for i in range(6):
            self.make_risk(title=f"خطر {i}", owner=self.owner.pk)
        self.assertEqual({user.pk: cost(user) for user in (self.qm, self.rag_lead)}, before)


class MatrixTests(RiskBase):
    def cells(self, user=None, **params):
        return self.api(user or self.qm).get(reverse("risk-matrix"), params).data

    def test_all_25_cells_are_always_there_worst_likelihood_first(self):
        data = self.cells()
        self.assertEqual((len(data["cells"]), data["total"]), (25, 0))
        self.assertEqual([(c["likelihood"], c["impact"]) for c in data["cells"]][:6], [(5, 1), (5, 2), (5, 3), (5, 4), (5, 5), (4, 1)])
        self.assertEqual({c["count"] for c in data["cells"]}, {0})
        self.assertEqual(data["levels"], {"low": 0, "medium": 0, "high": 0, "critical": 0})

    def test_counts_per_cell_and_per_level(self):
        self.make_risk(likelihood=3, impact=4)
        self.make_risk(likelihood=3, impact=4)
        self.make_risk(likelihood=5, impact=5)
        self.make_risk(likelihood=1, impact=1)
        data = self.cells()
        by = {(c["likelihood"], c["impact"]): c for c in data["cells"]}
        self.assertEqual((by[(3, 4)]["count"], by[(5, 5)]["count"], by[(1, 1)]["count"], by[(2, 2)]["count"]), (2, 1, 1, 0))
        self.assertEqual((by[(3, 4)]["score"], by[(3, 4)]["level"], by[(5, 5)]["level"]), (12, "high", "critical"))
        self.assertEqual((data["total"], data["levels"]), (4, {"low": 1, "medium": 0, "high": 2, "critical": 1}))

    def test_a_closed_risk_is_off_the_map_unless_asked_for(self):
        live = self.make_risk(likelihood=2, impact=2)
        gone = self.make_risk(likelihood=4, impact=5)
        accepted = self.make_risk(likelihood=1, impact=5)
        self.patch_risk(gone, status="CLOSED")
        self.patch_risk(accepted, status="ACCEPTED")
        self.assertEqual(self.cells()["total"], 2)  # identified and accepted stay on the register
        self.assertEqual(self.cells(status="CLOSED")["total"], 1)
        self.assertEqual(self.cells(status="MITIGATING")["total"], 0)
        self.assertEqual(self.cells(status="bogus")["total"], 2)  # an unknown status is ignored, not "nothing"
        self.assertEqual(live.status, RiskStatus.IDENTIFIED)

    def test_the_node_filter_covers_the_node_and_everything_beneath(self):
        self.make_risk()
        self.make_risk(user=self.ai_lead, owner_node=self.org.llm.pk)
        self.make_risk(user=self.qm, owner_node=self.org.dev.pk)
        self.assertEqual(self.cells(node=self.org.ai.pk)["total"], 2)
        self.assertEqual(self.cells(node=self.org.rag.pk)["total"], 1)
        self.assertEqual(self.cells(node=self.org.it.pk)["total"], 3)
        self.assertEqual(self.cells(node="x")["total"], 0)

    def test_the_matrix_is_not_mistaken_for_a_risk_id(self):
        self.assertEqual(self.api(self.qm).get("/api/v1/quality/risks/matrix/").status_code, 200)


class FeedTests(RiskBase):
    def setUp(self):
        super().setUp()
        self.risk = self.make_risk()
        self.patch_risk(self.risk, status="MITIGATING", likelihood=2)

    def rows(self, user, name, *args, **params):
        return self.api(user).get(reverse(name, args=args), params).data["results"]

    def test_a_risks_history_reads_newest_first_with_the_status_words(self):
        rows = self.rows(self.rag_lead, "risk-activity", self.risk.pk)
        self.assertEqual([r["kind"] for r in rows], ["risk_status_changed", "risk_assessed", "risk_created"])
        by_kind = {r["kind"]: r for r in rows}
        self.assertEqual((by_kind["risk_status_changed"]["from_status_label"], by_kind["risk_status_changed"]["to_status_label"]), (RiskStatus.IDENTIFIED.label, RiskStatus.MITIGATING.label))
        self.assertEqual(by_kind["risk_created"]["to_status_label"], RiskStatus.IDENTIFIED.label)
        self.assertEqual((by_kind["risk_assessed"]["note"], by_kind["risk_assessed"]["to_status_label"]), ("۳×۴ ← ۲×۴", ""))
        self.assertEqual((by_kind["risk_created"]["risk"], by_kind["risk_created"]["risk_code"], by_kind["risk_created"]["risk_title"]), (self.risk.pk, self.risk.code, self.risk.title))

    def test_a_history_you_may_not_read_is_a_404(self):
        for nobody in (self.dev_lead, self.outsider):
            self.assertEqual(self.api(nobody).get(reverse("risk-activity", args=[self.risk.pk])).status_code, 404)

    def test_the_cross_feed_covers_the_risks_you_may_read(self):
        elsewhere = self.make_risk(user=self.qm, owner_node=self.org.dev.pk)
        kinds = lambda user, **p: {(r["kind"], r["risk"]) for r in self.rows(user, "quality-activity", **p)}
        self.assertIn(("risk_created", elsewhere.pk), kinds(self.qm))
        self.assertEqual({risk for _, risk in kinds(self.rag_lead) if risk}, {self.risk.pk})
        self.assertEqual({risk for _, risk in kinds(self.dev_lead) if risk}, {elsewhere.pk})
        self.assertEqual(kinds(self.outsider), set())
        self.assertEqual({risk for _, risk in kinds(self.qm, risk=self.risk.pk)}, {self.risk.pk})
        self.assertEqual(kinds(self.outsider, risk=self.risk.pk), set())
        self.assertEqual(kinds(self.qm, risk="x"), set())


class ReviewTaskTests(RiskBase):
    def test_reminds_the_owner_once_per_review_date_never_twice(self):
        risk = self.make_risk(owner=self.owner.pk, review_on=_soon(1).isoformat())
        Notification.objects.all().delete()
        self.assertEqual(notification_tasks.check_risk_reviews(), 1)
        note = Notification.objects.get(kind=NotificationKind.RISK_REVIEW_DUE)
        self.assertEqual((note.recipient_id, note.url), (self.owner.pk, f"/quality/risks/{risk.pk}"))
        self.assertIn("نزدیک است", note.title)
        self.assertEqual(notification_tasks.check_risk_reviews(), 0)  # the dedupe key makes a re-run a no-op
        # The key carries the review *date*: put the date in the past and it is a different reminder, and
        # this one says so — but still only once.
        RiskItem.objects.filter(pk=risk.pk).update(review_on=_soon(-1))
        self.assertEqual(notification_tasks.check_risk_reviews(), 1)
        self.assertIn("گذشته است", Notification.objects.filter(kind=NotificationKind.RISK_REVIEW_DUE).latest("id").title)
        self.assertEqual(notification_tasks.check_risk_reviews(), 0)

    def test_a_new_review_date_after_a_review_is_a_new_reminder(self):
        risk = self.make_risk(owner=self.owner.pk, review_on=_soon(1).isoformat())
        notification_tasks.check_risk_reviews()
        self.patch_risk(risk, review_on=_soon(2).isoformat())
        self.assertEqual(notification_tasks.check_risk_reviews(), 1)
        self.assertEqual(Notification.objects.filter(kind=NotificationKind.RISK_REVIEW_DUE).count(), 2)

    def test_only_a_risk_still_on_the_register_with_a_date_that_is_near_or_past(self):
        self.make_risk(title="بدون تاریخ", owner=self.owner.pk)
        self.make_risk(title="دور", owner=self.owner.pk, review_on=_soon(60).isoformat())
        closed = self.make_risk(title="بسته", owner=self.owner.pk, review_on=_soon(1).isoformat())
        self.patch_risk(closed, status="CLOSED")
        self.assertEqual(notification_tasks.check_risk_reviews(), 0)
        accepted = self.make_risk(title="پذیرفته", owner=self.owner.pk, review_on=_soon(1).isoformat())
        self.patch_risk(accepted, status="ACCEPTED")
        self.assertEqual(notification_tasks.check_risk_reviews(), 1)  # an accepted risk still has to be looked at

    def test_with_nobody_named_the_leads_of_the_node_chain_are_told(self):
        self.make_risk(review_on=_soon(1).isoformat())
        Notification.objects.all().delete()
        self.assertEqual(notification_tasks.check_risk_reviews(), 2)
        self.assertEqual(sorted(_told(NotificationKind.RISK_REVIEW_DUE)), sorted([self.rag_lead.pk, self.ai_lead.pk]))

    def test_a_deactivated_owner_is_replaced_by_the_leads_and_with_no_leads_by_the_ceo(self):
        risk = self.make_risk(owner=self.owner.pk, review_on=_soon(1).isoformat())
        Notification.objects.all().delete()
        type(self.owner).objects.filter(pk=self.owner.pk).update(is_active=False)
        notification_tasks.check_risk_reviews()
        self.assertEqual(sorted(_told(NotificationKind.RISK_REVIEW_DUE)), sorted([self.rag_lead.pk, self.ai_lead.pk]))
        Membership.objects.filter(is_lead=True).delete()
        RiskItem.objects.filter(pk=risk.pk).update(review_on=_soon(2))
        Notification.objects.all().delete()
        notification_tasks.check_risk_reviews()
        self.assertEqual(_told(NotificationKind.RISK_REVIEW_DUE), [self.ceo.pk])

    def test_the_task_is_on_the_beat_schedule(self):
        from django.conf import settings

        entry = settings.CELERY_BEAT_SCHEDULE["notifications-check-risk-reviews"]
        self.assertEqual(entry["task"], "notifications.check_risk_reviews")


class GuardTests(RiskBase):
    def test_a_node_that_owns_a_risk_cannot_be_deleted_and_says_how_many(self):
        self.make_risk(user=self.ai_lead, owner_node=self.org.llm.pk)  # the lead of the unit above both sections
        self.make_risk(user=self.ai_lead, owner_node=self.org.llm.pk, title="دومی")
        response = self.api(self.ceo).delete(reverse("org-node-detail", args=[self.org.llm.pk]))
        self.assertEqual((response.status_code, response.data["code"], response.data["risks"]), (409, "node_not_empty", 2))

    def test_a_person_who_created_a_risk_cannot_be_deleted(self):
        lone = person()
        self.make_risk(user=self.qm)
        Membership.objects.filter(user=self.qm).delete()
        RiskItem.objects.update(created_by=lone)
        response = self.api(self.ceo).delete(reverse("personnel-detail", args=[lone.pk]))
        self.assertEqual((response.status_code, response.data["code"]), (409, "user_has_quality_records"))

    def test_a_person_who_is_only_an_owner_can_be_deleted_and_the_risk_stays(self):
        risk = self.make_risk(owner=self.owner.pk)
        self.assertEqual(self.api(self.ceo).delete(reverse("personnel-detail", args=[self.owner.pk])).status_code, 204)
        data = self.api(self.qm).get(self.risk_url(risk)).data
        self.assertEqual((data["owner"], data["owner_name"], data["owner_is_active"]), (None, None, None))
        self.assertEqual(risk.events.get().note, "۳×۴")  # the history did not hang on the owner

    def test_the_persian_digit_helper(self):
        from apps.core.text import to_persian_digits

        self.assertEqual(to_persian_digits("3×4 ← 10"), "۳×۴ ← ۱۰")
        self.assertEqual(to_persian_digits("abc"), "abc")
