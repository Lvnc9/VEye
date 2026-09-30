"""The dashboard's «منتظر اقدام شما» card (Phase 6). The counts/system-info views
are covered where they were built (documents/accounts tests)."""
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AccessLevel, AccessRoll, User
from apps.core.constants import DocumentCategory, DocumentGroup, DocumentStatus, SignOffRole
from apps.documents import test_support
from apps.documents.models import Document, SignOff

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "veye-dashboard-tests"}}


def user(code, roll, level=AccessLevel.LEVEL_2, **kw):
    return User.objects.create_user(national_code=code, password="pw-for-tests-123", full_name=f"کاربر {code}",
                                    access_roll=roll, access_level=level, **kw)


@override_settings(CACHES=LOCMEM)
class AwaitingCardTests(TestCase):
    """Who is waited for is the org chart's answer (documents/authority.py, Phase 14): the مسئول of a document's
    owner node writes it, the مسئول of a واحد / حوزه above it confirms, the مدیر عامل approves."""

    def setUp(self):
        cache.clear()
        self.org = test_support.ensure_org()
        self.author = user("8400000001", AccessRoll.GUILD)
        test_support.lead_of(self.author, self.org.rag)
        self.other_author = user("8400000002", AccessRoll.GUILD)
        test_support.lead_of(self.other_author, self.org.llm)
        self.confirmer = user("8400000003", AccessRoll.HEADQUARTERS)
        test_support.lead_of(self.confirmer, self.org.ai)
        self.approver = user("8400000004", AccessRoll.EMPLOYER, AccessLevel.LEVEL_1)  # the مدیر عامل
        self.n = 0

    def doc(self, status, by=None, saved=True, signers=(), node=None):
        self.n += 1
        d = Document.objects.create(
            category=DocumentCategory.INSIDE, title=f"سند {self.n}", group=DocumentGroup.PROCEDURE, number=self.n,
            revision=1, status=status, created_by=by or self.author, owner_node=node or self.org.rag,
            content_saved_at=timezone.now() if saved else None)
        for role, person in signers:
            SignOff.objects.create(document=d, role=role, name=person.full_name, position="س", signed_by=person)
        return d

    def card(self, who):
        client = APIClient()
        client.force_authenticate(who)
        return client.get(reverse("dashboard-awaiting"))

    def test_requires_authentication(self):
        self.assertEqual(APIClient().get(reverse("dashboard-awaiting")).status_code, 401)

    def test_an_author_sees_only_their_own_drafts_in_their_scope_that_have_a_saved_body(self):
        mine = self.doc(DocumentStatus.DRAFT)
        self.doc(DocumentStatus.DRAFT, by=self.other_author)      # someone else's draft
        self.doc(DocumentStatus.DRAFT, saved=False)               # nothing to submit yet
        self.doc(DocumentStatus.DRAFT, node=self.org.llm)         # mine, but in a بخش I do not lead
        self.doc(DocumentStatus.AWAITING_CONFIRMATION)            # not their step (a بخش's lead does not confirm)
        data = self.card(self.author).data
        self.assertEqual([i["id"] for i in data["items"]], [mine.pk])
        self.assertEqual((data["count"], data["by_step"]), (1, {"submit": 1, "confirm": 0, "approve": 0}))
        self.assertEqual((data["items"][0]["step"], data["items"][0]["step_label"]), ("submit", "ارسال برای تایید"))

    def test_a_confirmer_sees_what_awaits_confirmation_under_their_unit_including_their_own(self):
        theirs = self.doc(DocumentStatus.AWAITING_CONFIRMATION, signers=[(SignOffRole.CREATER, self.author)])
        own = self.doc(DocumentStatus.AWAITING_CONFIRMATION, by=self.confirmer, node=self.org.ai,
                       signers=[(SignOffRole.CREATER, self.confirmer)])  # they may write and confirm the same document
        self.doc(DocumentStatus.AWAITING_CONFIRMATION, node=self.org.deals)  # another واحد's
        self.doc(DocumentStatus.AWAITING_APPROVAL)                       # not their step
        ids = sorted(i["id"] for i in self.card(self.confirmer).data["items"])
        self.assertEqual(ids, sorted([theirs.pk, own.pk]))

    def test_the_managing_director_sees_everything_awaiting_approval(self):
        ready = self.doc(DocumentStatus.AWAITING_APPROVAL,
                         signers=[(SignOffRole.CREATER, self.author), (SignOffRole.CONFIRMER, self.confirmer)])
        elsewhere = self.doc(DocumentStatus.AWAITING_APPROVAL, node=self.org.deals)
        self.doc(DocumentStatus.AWAITING_CONFIRMATION)  # he may confirm too: it is listed as a confirm step
        data = self.card(self.approver).data
        self.assertEqual(sorted(i["id"] for i in data["items"] if i["step"] == "approve"), [ready.pk, elsewhere.pk])
        self.assertEqual(data["by_step"]["approve"], 2)

    def test_the_board_and_people_without_a_place_are_waited_for_by_nothing(self):
        chair = user("8400000006", AccessRoll.EMPLOYER, AccessLevel.LEVEL_2)
        member = user("8400000007", AccessRoll.GUILD)
        test_support.member_of(member, self.org.rag)
        for status in (DocumentStatus.DRAFT, DocumentStatus.AWAITING_CONFIRMATION, DocumentStatus.AWAITING_APPROVAL):
            self.doc(status)
        for who in (chair, member):
            self.assertEqual(self.card(who).data["count"], 0)

    def test_finished_and_obsolete_documents_are_never_listed(self):
        for status in (DocumentStatus.UNDER_CONTROL, DocumentStatus.OBSOLETE):
            self.doc(status)
        for who in (self.author, self.confirmer, self.approver):
            self.assertEqual(self.card(who).data["count"], 0)

    def test_the_card_agrees_with_the_registers_buttons(self):
        # Same verdict as row.workflow.can_act — one source of truth.
        self.doc(DocumentStatus.AWAITING_CONFIRMATION, signers=[(SignOffRole.CREATER, self.author)])
        self.doc(DocumentStatus.AWAITING_CONFIRMATION, by=self.confirmer, node=self.org.deals)
        client = APIClient()
        client.force_authenticate(self.confirmer)
        register = client.get(reverse("document-list")).data["results"]
        can_act = sorted(r["id"] for r in register if r["workflow"]["can_act"])
        self.assertEqual(sorted(i["id"] for i in client.get(reverse("dashboard-awaiting")).data["items"]), can_act)

    def test_lists_the_longest_waiting_first_but_caps_the_list_and_still_counts_all(self):
        with mock.patch("apps.dashboard.views.AWAITING_LIST_SIZE", 3):
            docs = [self.doc(DocumentStatus.AWAITING_CONFIRMATION, signers=[(SignOffRole.CREATER, self.author)])
                    for _ in range(5)]
            for i, d in enumerate(docs):  # docs[0] has been waiting the longest
                Document.objects.filter(pk=d.pk).update(updated_at=timezone.now() - timedelta(days=10 - i))
            data = self.card(self.confirmer).data
        self.assertEqual([i["id"] for i in data["items"]], [d.pk for d in docs[:3]])
        self.assertEqual(data["count"], 5)

    def test_costs_three_queries_however_many_documents(self):
        for _ in range(12):
            self.doc(DocumentStatus.AWAITING_CONFIRMATION, signers=[(SignOffRole.CREATER, self.author)])
        client = APIClient()
        client.force_authenticate(self.confirmer)
        with self.assertNumQueries(3):  # the person's lead nodes + documents (owner node joined) + their sign-offs
            client.get(reverse("dashboard-awaiting"))

    def test_a_user_with_no_chart_authority_gets_an_empty_card(self):
        nobody = user("8400000005", "NONE")
        self.doc(DocumentStatus.AWAITING_CONFIRMATION)
        self.assertEqual(self.card(nobody).data, {"count": 0, "by_step": {"submit": 0, "confirm": 0, "approve": 0}, "items": []})


@override_settings(CACHES=LOCMEM, INBOX_DUE_SOON_DAYS=3)
class InboxBadgeTests(TestCase):
    """GET /dashboard/inbox/ (Phase 9.3): the کارتابل badge — unread chat + documents awaiting my step
    + my ریزهدف due soon or overdue — and the ریزهدف rows of «منتظر اقدام»."""

    def setUp(self):
        from apps.chat.tests import ChatWorld

        cache.clear()
        world = ChatWorld()
        world.build_world()
        self.w = world
        self.today = timezone.localdate()

    def inbox(self, who):
        client = APIClient()
        client.force_authenticate(who)
        return client.get(reverse("dashboard-inbox"))

    def project_with(self, assignee, *days_from_today, section=None):
        from apps.projects import services as projects
        from apps.projects.models import Objective

        project = projects.create_project(
            actor=self.w.s1a, section=section or self.w.s1, name=f"پروژه {Objective.objects.count()}",
            members=[{"user": assignee}],
            objectives=[
                {"title": f"ریزهدف {i}", "assignees": [assignee], "due_on": self.today + timedelta(days=30)}
                for i, _ in enumerate(days_from_today)
            ],
        )
        for objective, days in zip(project.objectives.order_by("id"), days_from_today):
            Objective.objects.filter(pk=objective.pk).update(due_on=self.today + timedelta(days=days))
        return project

    def test_requires_authentication(self):
        self.assertEqual(APIClient().get(reverse("dashboard-inbox")).status_code, 401)

    def test_nothing_to_do_is_all_zeros(self):
        data = self.inbox(self.w.nobody).data
        self.assertEqual(
            {k: data[k] for k in ("unread_messages", "awaiting_documents", "due_objectives", "total")},
            {"unread_messages": 0, "awaiting_documents": 0, "due_objectives": 0, "total": 0},
        )
        self.assertEqual(data["objectives"], [])

    def test_unread_messages_follow_chats_own_definition(self):
        from apps.chat import services as chat
        from apps.chat.tests import channel

        dm, _ = chat.open_direct(actor=self.w.s1a, other=self.w.s1b)
        chat.send_message(dm, sender=self.w.s1a, body="یک")
        chat.send_message(channel(self.w.s1), sender=self.w.s1a, body="دو")
        chat.send_message(channel(self.w.u2), sender=self.w.u2m, body="not theirs")
        self.assertEqual(self.inbox(self.w.s1b).data["unread_messages"], 2)
        self.assertEqual(self.inbox(self.w.s1a).data["unread_messages"], 0)  # their own words
        self.assertEqual(self.inbox(self.w.ceo).data["unread_messages"], 0)  # not in the ceo's DMs; S1 not opened

    def test_awaiting_documents_is_the_same_number_as_the_card(self):
        confirmer = self.w.u1lead  # leads the واحد above the بخش that owns the document
        author = user("8400000014", AccessRoll.GUILD)
        doc = Document.objects.create(
            category=DocumentCategory.INSIDE, title="سند", group=DocumentGroup.PROCEDURE, number=1, revision=1,
            status=DocumentStatus.AWAITING_CONFIRMATION, created_by=author, content_saved_at=timezone.now(),
            owner_node=self.w.s1,
        )
        SignOff.objects.create(document=doc, role=SignOffRole.CREATER, name=author.full_name, position="س", signed_by=author)
        client = APIClient()
        client.force_authenticate(confirmer)
        card = client.get(reverse("dashboard-awaiting")).data["count"]
        self.assertEqual((card, self.inbox(confirmer).data["awaiting_documents"]), (1, 1))

    def test_due_objectives_are_mine_open_live_and_due_within_the_window_or_overdue(self):
        from apps.projects import services as projects
        from apps.projects.models import Objective, ObjectiveStatus

        mine = self.project_with(self.w.s1b, -2, 0, 3, 4)                # overdue, today, edge, too far
        self.project_with(self.w.s1a, 1)                                  # someone else's
        done = self.project_with(self.w.s1b, 1)
        Objective.objects.filter(project=done).update(status=ObjectiveStatus.DONE)
        cancelled = self.project_with(self.w.s1b, 1)
        Objective.objects.filter(project=cancelled).update(status=ObjectiveStatus.CANCELLED)
        archived = self.project_with(self.w.s1b, 1)
        projects.archive_project(archived, actor=self.w.s1a)

        data = self.inbox(self.w.s1b).data
        self.assertEqual(data["due_objectives"], 3)
        self.assertEqual([o["title"] for o in data["objectives"]], ["ریزهدف 0", "ریزهدف 1", "ریزهدف 2"])
        self.assertEqual([o["is_overdue"] for o in data["objectives"]], [True, False, False])
        self.assertEqual(data["objectives"][0]["project"], {"id": mine.pk, "name": mine.name})
        self.assertEqual(data["objectives"][0]["status_label"], "انجام نشده")

    def test_the_badge_is_the_sum_and_the_list_is_capped_but_the_count_is_not(self):
        from apps.chat import services as chat

        dm, _ = chat.open_direct(actor=self.w.s1a, other=self.w.s1b)
        chat.send_message(dm, sender=self.w.s1a, body="یک")
        with mock.patch("apps.dashboard.views.INBOX_OBJECTIVES_SIZE", 2):
            self.project_with(self.w.s1b, 0, 1, 2)
            data = self.inbox(self.w.s1b).data
        self.assertEqual((data["due_objectives"], len(data["objectives"])), (3, 2))
        self.assertEqual(data["total"], data["unread_messages"] + data["awaiting_documents"] + data["due_objectives"])
        self.assertEqual(data["total"], 4)
