"""Slice 9.1: conversations, participants, messages — the models, eager node channels, DM
de-duplication and who may read what."""
from unittest import mock

from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse

from apps.accounts.models import AccessLevel, AccessRoll
from apps.core.exceptions import ConflictError
from apps.organization import memberships, tree
from apps.organization.models import Membership, OrgNode
from apps.organization.tests import SampleTree, Threaded, add, join, make_company, person
from apps.organization.tests import ApiTestCase as OrgApiTestCase
from rest_framework.exceptions import ValidationError

from . import services
from .access import ChatAccess
from .models import Conversation, ConversationKind, ConversationParticipant, Message, MessageKind


def channel(node) -> Conversation:
    return Conversation.objects.get(kind=ConversationKind.NODE, node=node)


def say(conversation, sender, body="سلام"):
    """A raw message row (sending is slice 9.2's service)."""
    return Message.objects.create(conversation=conversation, sender=sender, sender_name=sender.full_name, body=body)


class ChatWorld(SampleTree):
    """company ─ D1 ─ U1 ─ S1 · U2   D2 ─ U3   U4, and:
         ceo      lead of the company node (every capability)
         u1lead   lead of U1
         d2lead   lead of D2
         s1a/s1b  members of S1
         u2m      member of U2
         nobody   no membership at all"""

    def build_world(self):
        self.build()
        self.ceo = person("9700000001", "مدیر عامل", roll=AccessRoll.EMPLOYER, level=AccessLevel.LEVEL_1)
        self.u1lead = person("9700000002", "مسئول واحد فروش")
        self.d2lead = person("9700000003", "مسئول حوزه دو")
        self.s1a = person("9700000004", "عضو یک")
        self.s1b = person("9700000005", "عضو دو")
        self.u2m = person("9700000006", "عضو واحد مالی")
        self.nobody = person("9700000007", "بی‌جایگاه")
        join(self.ceo, self.root, is_lead=True)
        join(self.u1lead, self.u1, is_lead=True)
        join(self.d2lead, self.d2, is_lead=True)
        join(self.s1a, self.s1)
        join(self.s1b, self.s1)
        join(self.u2m, self.u2)

    def reads(self, user, node) -> bool:
        return ChatAccess(user).can_read_node(node)

    def visible(self, user) -> set[int]:
        return set(ChatAccess(user).visible_conversations().values_list("pk", flat=True))

    def listed(self, user) -> set[int]:
        return set(ChatAccess(user).listed_conversations().values_list("pk", flat=True))


# ---------------------------------------------------------------------------
# The schema
# ---------------------------------------------------------------------------


class ConstraintTests(ChatWorld, TestCase):
    def setUp(self):
        self.build_world()

    def assert_refused(self, constraint, **fields):
        with self.assertRaises(IntegrityError) as caught, transaction.atomic():
            Conversation.objects.create(**fields)
        self.assertIn(constraint, str(caught.exception))

    def test_a_node_has_exactly_one_channel(self):
        self.assert_refused("uniq_node_conversation", kind=ConversationKind.NODE, node=self.s1)

    def test_a_pair_has_exactly_one_direct_conversation(self):
        services.open_direct(actor=self.s1a, other=self.s1b)
        self.assert_refused(
            "uniq_direct_conversation",
            kind=ConversationKind.DIRECT,
            direct_key=services.direct_key(self.s1a.pk, self.s1b.pk),
        )

    def test_the_shape_of_each_kind_is_enforced(self):
        self.assert_refused("conversation_shape", kind=ConversationKind.DIRECT, direct_key="1:2", node=self.u4)
        self.assert_refused("conversation_shape", kind=ConversationKind.DIRECT, direct_key="")
        self.assert_refused("conversation_shape", kind=ConversationKind.NODE, node=None)
        fresh = add("UNIT", "واحد تازه", self.root)
        Conversation.objects.filter(node=fresh).delete()
        self.assert_refused("conversation_shape", kind=ConversationKind.NODE, node=fresh, direct_key="1:2")

    def test_a_person_is_a_participant_once(self):
        conversation = channel(self.s1)
        ConversationParticipant.objects.create(conversation=conversation, user=self.s1a)
        with self.assertRaises(IntegrityError) as caught, transaction.atomic():
            ConversationParticipant.objects.create(conversation=conversation, user=self.s1a)
        self.assertIn("uniq_conversation_participant", str(caught.exception))

    def test_a_system_line_has_no_sender(self):
        with self.assertRaises(IntegrityError) as caught, transaction.atomic():
            Message.objects.create(
                conversation=channel(self.s1), sender=self.s1a, sender_name="x", body="x", kind=MessageKind.SYSTEM
            )
        self.assertIn("message_system_has_no_sender", str(caught.exception))
        Message.objects.create(conversation=channel(self.s1), sender_name="سیستم", body="x", kind=MessageKind.SYSTEM)

    def test_deleted_by_needs_deleted_at(self):
        with self.assertRaises(IntegrityError) as caught, transaction.atomic():
            Message.objects.create(
                conversation=channel(self.s1), sender=self.s1a, sender_name="x", body="x", deleted_by=self.s1a
            )
        self.assertIn("message_deleted_by_needs_deleted_at", str(caught.exception))


# ---------------------------------------------------------------------------
# Node channels live and die with their node
# ---------------------------------------------------------------------------


class NodeChannelTests(ChatWorld, TestCase):
    def setUp(self):
        self.build_world()

    def test_every_node_including_the_company_has_exactly_one_channel_from_birth(self):
        for node in OrgNode.objects.all():
            self.assertEqual(Conversation.objects.filter(kind=ConversationKind.NODE, node=node).count(), 1, node)
        self.assertEqual(Conversation.objects.filter(kind=ConversationKind.NODE).count(), OrgNode.objects.count())

    def test_the_channel_is_made_in_the_nodes_own_transaction(self):
        with mock.patch("apps.chat.services.create_node_conversation", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                add("UNIT", "واحد ناکام", self.root)
        self.assertFalse(OrgNode.objects.filter(name="واحد ناکام").exists())

    def test_a_node_that_predates_chat_gets_its_channel_on_first_open(self):
        Conversation.objects.filter(node=self.u4).delete()
        first = services.node_conversation(self.u4)
        self.assertEqual(services.node_conversation(self.u4), first)
        self.assertEqual(Conversation.objects.filter(node=self.u4).count(), 1)

    def test_deleting_an_empty_node_removes_its_silent_channel(self):
        services.ensure_participant(channel(self.u4), self.ceo)
        tree.delete_node(self.u4)
        self.assertFalse(OrgNode.objects.filter(pk=self.u4.pk).exists())
        self.assertFalse(Conversation.objects.filter(node_id=self.u4.pk).exists())
        self.assertFalse(ConversationParticipant.objects.filter(conversation__node_id=self.u4.pk).exists())

    def test_a_node_whose_channel_has_messages_cannot_be_deleted(self):
        say(channel(self.u4), self.ceo)
        with self.assertRaises(ConflictError) as caught:
            tree.delete_node(self.u4)
        self.assertEqual(caught.exception.payload["code"], "node_not_empty")
        self.assertEqual(caught.exception.payload["messages"], 1)
        self.assertTrue(OrgNode.objects.filter(pk=self.u4.pk).exists())
        self.assertTrue(Conversation.objects.filter(node=self.u4).exists())

    def test_tombstoned_messages_still_block_but_system_lines_do_not(self):
        Message.objects.create(conversation=channel(self.u4), sender_name="سیستم", body="x", kind=MessageKind.SYSTEM)
        self.assertEqual(tree.node_blockers(self.u4)["messages"], 0)
        message = say(channel(self.u4), self.ceo)
        Message.objects.filter(pk=message.pk).update(deleted_at=message.created_at)
        self.assertEqual(tree.node_blockers(self.u4)["messages"], 1)

    def test_a_system_only_channel_is_deleted_with_its_node(self):
        Message.objects.create(conversation=channel(self.u4), sender_name="سیستم", body="x", kind=MessageKind.SYSTEM)
        tree.delete_node(self.u4)
        self.assertFalse(Message.objects.filter(conversation__node_id=self.u4.pk).exists())


# ---------------------------------------------------------------------------
# Direct conversations
# ---------------------------------------------------------------------------


class DirectConversationTests(ChatWorld, TestCase):
    def setUp(self):
        self.build_world()

    def test_the_key_is_canonical_and_zero_padded(self):
        self.assertEqual(services.direct_key(42, 7), "0000000007:0000000042")
        self.assertEqual(services.direct_key(7, 42), services.direct_key(42, 7))

    def test_opening_creates_it_once_with_both_participants_whichever_side_opens(self):
        first, created = services.open_direct(actor=self.s1a, other=self.u2m)
        self.assertTrue(created)
        self.assertEqual(
            set(first.participants.values_list("user_id", flat=True)), {self.s1a.pk, self.u2m.pk}
        )
        again, created_again = services.open_direct(actor=self.u2m, other=self.s1a)
        self.assertEqual((again.pk, created_again), (first.pk, False))
        self.assertEqual(Conversation.objects.filter(kind=ConversationKind.DIRECT).count(), 1)
        self.assertEqual(first.created_by, self.s1a)

    def test_anyone_may_message_anyone_even_without_a_place_in_the_chart(self):
        conversation, created = services.open_direct(actor=self.nobody, other=self.ceo)
        self.assertTrue(created)

    def test_you_cannot_message_yourself(self):
        with self.assertRaises(ValidationError):
            services.open_direct(actor=self.s1a, other=self.s1a)

    def test_an_inactive_person_cannot_be_messaged(self):
        self.s1b.is_active = False
        self.s1b.save(update_fields=["is_active"])
        with self.assertRaises(ConflictError) as caught:
            services.open_direct(actor=self.s1a, other=self.s1b)
        self.assertEqual(caught.exception.payload["code"], "user_inactive")
        self.assertFalse(Conversation.objects.filter(kind=ConversationKind.DIRECT).exists())

    def test_a_lost_race_returns_the_winners_row(self):
        """Simulate the loser of a race: the pre-read sees nothing, the insert hits the index."""
        winner, _ = services.open_direct(actor=self.s1a, other=self.s1b)
        real_filter = Conversation.objects.filter
        calls = []

        def blind_first_read(*args, **kwargs):
            queryset = real_filter(*args, **kwargs)
            if not calls:
                calls.append(1)
                return queryset.none()
            return queryset

        with mock.patch.object(Conversation.objects, "filter", side_effect=blind_first_read):
            conversation, created = services.open_direct(actor=self.s1b, other=self.s1a)
        self.assertEqual((conversation.pk, created), (winner.pk, False))
        self.assertEqual(ConversationParticipant.objects.filter(conversation=winner).count(), 2)

    def test_an_unrelated_integrity_error_stays_loud(self):
        with mock.patch.object(
            ConversationParticipant.objects, "bulk_create", side_effect=IntegrityError("something else")
        ):
            with self.assertRaises(IntegrityError):
                services.open_direct(actor=self.s1a, other=self.s1b)


# ---------------------------------------------------------------------------
# Who may read what
# ---------------------------------------------------------------------------


class AccessTests(ChatWorld, TestCase):
    def setUp(self):
        self.build_world()

    def test_members_read_their_own_nodes_channel_only(self):
        self.assertTrue(self.reads(self.s1a, self.s1))
        self.assertFalse(self.reads(self.s1a, self.u1))  # a member below is not a member above
        self.assertFalse(self.reads(self.s1a, self.u2))
        self.assertFalse(self.reads(self.u2m, self.s1))

    def test_a_lead_reads_every_channel_in_their_branch_and_nothing_beside_it(self):
        self.assertTrue(self.reads(self.u1lead, self.u1))
        self.assertTrue(self.reads(self.u1lead, self.s1))
        self.assertFalse(self.reads(self.u1lead, self.d1))  # above them
        self.assertFalse(self.reads(self.u1lead, self.u2))  # a sibling
        self.assertTrue(self.reads(self.d2lead, self.u3))
        self.assertFalse(self.reads(self.d2lead, self.s1))  # the other branch

    def test_the_company_lead_reads_every_group_channel(self):
        for node in OrgNode.objects.all():
            self.assertTrue(self.reads(self.ceo, node), node)

    def test_the_company_channel_is_open_to_everyone_placed_in_the_chart(self):
        for user in (self.s1a, self.u2m, self.u1lead, self.d2lead, self.ceo):
            self.assertTrue(self.reads(user, self.root), user)
        self.assertFalse(self.reads(self.nobody, self.root))

    def test_someone_with_no_place_reads_no_group_channel(self):
        self.assertFalse(any(self.reads(self.nobody, node) for node in OrgNode.objects.all()))
        self.assertEqual(self.visible(self.nobody), set())

    def test_lead_authority_ends_when_the_led_node_is_archived(self):
        tree.archive_node(self.s1)
        tree.archive_node(self.u1)
        self.assertFalse(self.reads(self.u1lead, self.s1))
        self.assertTrue(self.reads(self.u1lead, self.u1))  # still a member of U1 itself

    def test_members_of_an_archived_node_keep_reading_its_history(self):
        tree.archive_node(self.s1)
        self.assertTrue(self.reads(self.s1a, self.s1))

    def test_access_follows_membership_at_request_time(self):
        self.assertTrue(self.reads(self.u2m, self.u2))
        memberships.remove_membership(Membership.objects.get(user=self.u2m, node=self.u2))
        self.assertFalse(self.reads(self.u2m, self.u2))
        memberships.add_membership(user=self.u2m, node=self.s1)
        self.assertTrue(self.reads(self.u2m, self.s1))

    def test_a_dm_is_readable_by_its_two_people_and_by_no_one_else_not_even_the_company_lead(self):
        dm, _ = services.open_direct(actor=self.s1a, other=self.s1b)
        self.assertIn(dm.pk, self.visible(self.s1a))
        self.assertIn(dm.pk, self.visible(self.s1b))
        for other in (self.ceo, self.u1lead, self.u2m, self.nobody):
            self.assertNotIn(dm.pk, self.visible(other), other)
            self.assertFalse(ChatAccess(other).can_read(dm), other)

    def test_visible_matches_can_read_for_every_conversation_and_person(self):
        services.open_direct(actor=self.s1a, other=self.u2m)
        services.open_direct(actor=self.ceo, other=self.d2lead)
        people = (self.ceo, self.u1lead, self.d2lead, self.s1a, self.s1b, self.u2m, self.nobody)
        for user in people:
            access = ChatAccess(user)
            expected = {c.pk for c in Conversation.objects.all() if access.can_read(c)}
            self.assertEqual(self.visible(user), expected, user)

    def test_a_member_lists_their_own_channels_the_company_channel_and_their_dms(self):
        dm, _ = services.open_direct(actor=self.s1a, other=self.u2m)
        self.assertEqual(self.listed(self.s1a), {channel(self.s1).pk, channel(self.root).pk, dm.pk})

    def test_a_lead_lists_a_lower_channel_only_once_they_have_opened_it(self):
        self.assertNotIn(channel(self.s1).pk, self.listed(self.u1lead))
        self.assertIn(channel(self.u1).pk, self.listed(self.u1lead))
        services.open_node_conversation(actor=self.u1lead, node=self.s1)
        self.assertIn(channel(self.s1).pk, self.listed(self.u1lead))

    def test_a_channel_opened_earlier_drops_out_of_the_list_when_access_ends(self):
        services.open_node_conversation(actor=self.u2m, node=self.u2)
        memberships.remove_membership(Membership.objects.get(user=self.u2m, node=self.u2))
        self.assertNotIn(channel(self.u2).pk, self.listed(self.u2m))
        self.assertTrue(ConversationParticipant.objects.filter(conversation=channel(self.u2), user=self.u2m).exists())

    def test_the_access_check_costs_two_queries_then_none(self):
        access = ChatAccess(self.u1lead)
        with self.assertNumQueries(2):  # membership node ids + lead paths
            access.can_read_node(self.s1)
            access.can_read_node(self.u1)
            access.can_read_node(self.root)
        with self.assertNumQueries(0):
            for node in (self.s1, self.u1, self.u2, self.d1, self.root):
                access.can_read_node(node)


# ---------------------------------------------------------------------------
# The API
# ---------------------------------------------------------------------------


class ChatApiTests(ChatWorld, OrgApiTestCase):
    def setUp(self):
        super().setUp()
        self.build_world()

    def ids(self, response):
        return [row["id"] for row in response.data["results"]]

    def test_it_needs_a_login(self):
        self.assertEqual(self.client.get(reverse("conversation-list")).status_code, 401)
        self.assertEqual(self.client.post(reverse("conversation-direct"), {"user": self.s1b.pk}).status_code, 401)

    def test_the_list_is_the_listed_set_most_recent_activity_first(self):
        dm, _ = services.open_direct(actor=self.s1a, other=self.u2m)
        Conversation.objects.filter(pk=channel(self.root).pk).update(last_message_at="2026-09-01T10:00:00Z")
        Conversation.objects.filter(pk=dm.pk).update(last_message_at="2026-09-02T10:00:00Z")
        response = self.as_(self.s1a).get(reverse("conversation-list"))
        self.assertEqual(response.status_code, 200)
        # used ones newest first, then never-used ones (newest id first)
        self.assertEqual(self.ids(response), [dm.pk, channel(self.root).pk, channel(self.s1).pk])

    def test_a_dm_row_names_the_other_person(self):
        services.open_direct(actor=self.s1a, other=self.u2m)
        row = next(r for r in self.as_(self.s1a).get(reverse("conversation-list")).data["results"] if r["kind"] == "DIRECT")
        self.assertEqual(row["title"], self.u2m.full_name)
        self.assertEqual(row["counterpart"]["id"], self.u2m.pk)
        self.assertEqual(row["kind_label"], "خصوصی")
        self.assertTrue(row["can_post"])
        self.assertIsNone(row["node"])

    def test_group_rows_carry_their_node_and_flag_the_company_channel(self):
        rows = {r["id"]: r for r in self.as_(self.s1a).get(reverse("conversation-list")).data["results"]}
        company, section = rows[channel(self.root).pk], rows[channel(self.s1).pk]
        self.assertTrue(company["is_company_channel"])
        self.assertFalse(section["is_company_channel"])
        self.assertEqual((section["title"], section["node"], section["node_kind"]), (self.s1.name, self.s1.pk, "SECTION"))
        self.assertIsNone(section["counterpart"])

    def test_an_archived_nodes_channel_is_read_only(self):
        tree.archive_node(self.s1)
        response = self.as_(self.s1a).get(reverse("conversation-detail", args=[channel(self.s1).pk]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["can_post"])

    def test_a_dm_with_a_deactivated_person_is_read_only(self):
        dm, _ = services.open_direct(actor=self.s1a, other=self.s1b)
        self.s1b.is_active = False
        self.s1b.save(update_fields=["is_active"])
        response = self.as_(self.s1a).get(reverse("conversation-detail", args=[dm.pk]))
        self.assertFalse(response.data["can_post"])

    def test_someone_elses_dm_is_a_404_even_for_the_company_lead(self):
        dm, _ = services.open_direct(actor=self.s1a, other=self.s1b)
        for user in (self.ceo, self.u1lead, self.u2m):
            self.assertEqual(self.as_(user).get(reverse("conversation-detail", args=[dm.pk])).status_code, 404, user)
        self.assertEqual(self.as_(self.s1b).get(reverse("conversation-detail", args=[dm.pk])).status_code, 200)

    def test_a_lead_can_open_a_lower_channel_that_is_not_in_their_list_yet(self):
        """Being listed and being readable are different sets: the list is a convenience."""
        url = reverse("conversation-detail", args=[channel(self.s1).pk])
        self.assertEqual(self.as_(self.u1lead).get(url).status_code, 200)
        self.assertEqual(self.as_(self.ceo).get(url).status_code, 200)

    def test_a_group_channel_you_may_not_read_is_a_404(self):
        response = self.as_(self.u2m).get(reverse("conversation-detail", args=[channel(self.s1).pk]))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], "مورد درخواستی یافت نشد.")

    def test_opening_a_dm_is_201_then_200_with_the_same_conversation(self):
        first = self.as_(self.s1a).post(reverse("conversation-direct"), {"user": self.u2m.pk})
        self.assertEqual(first.status_code, 201)
        second = self.as_(self.u2m).post(reverse("conversation-direct"), {"user": self.s1a.pk})
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(second.data["title"], self.s1a.full_name)

    def test_opening_a_dm_with_nobody_yourself_or_an_inactive_person(self):
        self.as_(self.s1a)
        self.assertEqual(self.client.post(reverse("conversation-direct"), {"user": 999999}).status_code, 404)
        self.assertEqual(self.client.post(reverse("conversation-direct"), {"user": self.s1a.pk}).status_code, 400)
        self.assertEqual(self.client.post(reverse("conversation-direct"), {}).status_code, 400)
        self.s1b.is_active = False
        self.s1b.save(update_fields=["is_active"])
        response = self.client.post(reverse("conversation-direct"), {"user": self.s1b.pk})
        self.assertEqual((response.status_code, response.data["code"]), (409, "user_inactive"))

    @override_settings(RATELIMIT_ENABLE=True, CHAT_OPEN_DIRECT_RATELIMIT_RATE="2/m")
    def test_opening_dms_is_rate_limited_per_person(self):
        self.as_(self.s1a)
        codes = [
            self.client.post(reverse("conversation-direct"), {"user": other.pk}).status_code
            for other in (self.s1b, self.u2m, self.ceo)
        ]
        self.assertEqual(codes, [201, 201, 403])
        # another person has their own budget
        self.assertEqual(self.as_(self.u2m).post(reverse("conversation-direct"), {"user": self.ceo.pk}).status_code, 201)

    def test_opening_a_group_channel_puts_it_in_a_leads_list(self):
        self.as_(self.u1lead)
        self.assertNotIn(channel(self.s1).pk, self.ids(self.client.get(reverse("conversation-list"))))
        response = self.client.post(reverse("conversation-node"), {"node": self.s1.pk})
        self.assertEqual((response.status_code, response.data["id"]), (200, channel(self.s1).pk))
        self.assertIn(channel(self.s1).pk, self.ids(self.client.get(reverse("conversation-list"))))

    def test_opening_a_group_channel_you_may_not_read_is_a_403_that_says_why(self):
        response = self.as_(self.u2m).post(reverse("conversation-node"), {"node": self.s1.pk})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["detail"], "شما عضو این گره یا مسئول گره‌های بالادستی آن نیستید.")
        self.assertFalse(ConversationParticipant.objects.filter(user=self.u2m, conversation=channel(self.s1)).exists())
        self.assertEqual(self.client.post(reverse("conversation-node"), {"node": 999999}).status_code, 404)

    def test_opening_the_channel_of_a_node_that_predates_chat_creates_it(self):
        Conversation.objects.filter(node=self.s1).delete()
        response = self.as_(self.s1a).post(reverse("conversation-node"), {"node": self.s1.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], channel(self.s1).pk)

    def test_deleting_a_node_with_messages_is_a_409_with_the_count(self):
        say(channel(self.u4), self.ceo)
        say(channel(self.u4), self.ceo, "دوم")
        response = self.as_(self.ceo).delete(reverse("org-node-detail", args=[self.u4.pk]))
        self.assertEqual((response.status_code, response.data["code"], response.data["messages"]), (409, "node_not_empty", 2))

    def test_the_list_costs_a_fixed_number_of_queries(self):
        for other in (self.s1b, self.u2m, self.ceo, self.d2lead):
            services.open_direct(actor=self.s1a, other=other)
        self.as_(self.s1a)
        # count, page, participants prefetch; plus membership ids + lead paths
        with self.assertNumQueries(5):
            self.client.get(reverse("conversation-list"))


# ---------------------------------------------------------------------------
# Real threads (Postgres)
# ---------------------------------------------------------------------------


@skipUnlessDBFeature("has_select_for_update")
class ChatConcurrencyTests(Threaded, TransactionTestCase):
    def setUp(self):
        self.root = make_company()
        self.unit = add("UNIT", "واحد", self.root)
        self.a = person("9710000001", "الف")
        self.b = person("9710000002", "ب")

    def test_concurrent_openers_of_one_dm_get_one_conversation_from_either_side(self):
        def worker(i):
            actor, other = (self.a, self.b) if i % 2 else (self.b, self.a)
            return services.open_direct(actor=actor, other=other)[0].pk

        results = self.run_concurrently(worker, 8)
        self.assertTrue(all(kind == "ok" for kind, _ in results), results)
        self.assertEqual(len({pk for _, pk in results}), 1, results)
        self.assertEqual(Conversation.objects.filter(kind=ConversationKind.DIRECT).count(), 1)
        self.assertEqual(ConversationParticipant.objects.count(), 2)

    def test_concurrent_first_opens_of_a_channel_make_one_participant_row(self):
        conversation = Conversation.objects.get(node=self.unit)
        results = self.run_concurrently(lambda i: services.ensure_participant(conversation, self.a).pk, 6)
        self.assertTrue(all(kind == "ok" for kind, _ in results), results)
        self.assertEqual(ConversationParticipant.objects.filter(conversation=conversation, user=self.a).count(), 1)

    def test_concurrent_first_opens_of_a_pre_chat_node_make_one_channel(self):
        Conversation.objects.filter(node=self.unit).delete()
        results = self.run_concurrently(lambda i: services.node_conversation(self.unit).pk, 6)
        self.assertTrue(all(kind == "ok" for kind, _ in results), results)
        self.assertEqual(len({pk for _, pk in results}), 1)
        self.assertEqual(Conversation.objects.filter(node=self.unit).count(), 1)
