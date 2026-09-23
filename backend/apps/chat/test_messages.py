"""Slice 9.2: sending, cursor paging and polling, read marks, tombstones, unread counts, rate limits,
and the system lines membership changes write."""
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.exceptions import ConflictError
from apps.organization import memberships, tree
from apps.organization.models import Membership
from apps.organization.tests import ApiTestCase as OrgApiTestCase
from apps.organization.tests import Threaded, add, make_company, person

from . import services
from .access import ChatAccess
from .models import Conversation, ConversationParticipant, Message, MessageKind
from .queries import unread_total, with_viewer_state
from .services import MESSAGE_MAX_LENGTH
from .tests import ChatWorld, channel


def texts(conversation):
    return list(conversation.messages.filter(kind=MessageKind.TEXT).values_list("body", flat=True))


def unread(user, conversation) -> int:
    return with_viewer_state(Conversation.objects.filter(pk=conversation.pk), user).get().unread_count


class SendTests(ChatWorld, TestCase):
    def setUp(self):
        self.build_world()
        self.dm, _ = services.open_direct(actor=self.s1a, other=self.s1b)

    def test_a_message_snapshots_its_sender_and_becomes_the_conversations_newest(self):
        message = services.send_message(self.dm, sender=self.s1a, body="  سلام  ")
        self.assertEqual((message.body, message.sender_name, message.sender_title), ("سلام", self.s1a.full_name, self.s1a.title))
        self.dm.refresh_from_db()
        self.assertEqual((self.dm.last_message_id, self.dm.last_message_at), (message.pk, message.created_at))

    def test_the_senders_own_message_is_read_for_them(self):
        message = services.send_message(self.dm, sender=self.s1a, body="الف")
        mark = ConversationParticipant.objects.get(conversation=self.dm, user=self.s1a).last_read_message_id
        self.assertEqual(mark, message.pk)
        self.assertEqual(unread(self.s1a, self.dm), 0)
        self.assertEqual(unread(self.s1b, self.dm), 1)

    def test_an_empty_or_too_long_message_is_refused(self):
        for body in ("", "   \n "):
            with self.assertRaises(ValidationError):
                services.send_message(self.dm, sender=self.s1a, body=body)
        with self.assertRaises(ValidationError):
            services.send_message(self.dm, sender=self.s1a, body="x" * (MESSAGE_MAX_LENGTH + 1))
        services.send_message(self.dm, sender=self.s1a, body="x" * MESSAGE_MAX_LENGTH)

    def test_an_archived_nodes_channel_refuses_new_messages(self):
        tree.archive_node(self.s1)
        with self.assertRaises(ConflictError) as caught:
            services.send_message(channel(self.s1), sender=self.s1a, body="الف")
        self.assertEqual(caught.exception.payload["code"], "conversation_read_only")

    def test_a_dm_with_a_deactivated_person_refuses_new_messages(self):
        self.s1b.is_active = False
        self.s1b.save(update_fields=["is_active"])
        with self.assertRaises(ConflictError) as caught:
            services.send_message(self.dm, sender=self.s1a, body="الف")
        self.assertEqual(caught.exception.payload["code"], "user_inactive")


class SystemLineTests(ChatWorld, TestCase):
    def setUp(self):
        self.build_world()

    def system_lines(self, node):
        return list(channel(node).messages.filter(kind=MessageKind.SYSTEM).values_list("body", flat=True))

    def test_joining_and_leaving_a_node_are_written_to_its_channel(self):
        newcomer = person("9720000001", "تازه‌وارد")
        membership = memberships.add_membership(user=newcomer, node=self.u4)
        memberships.remove_membership(membership)
        self.assertEqual(self.system_lines(self.u4), ["تازه‌وارد به گفتگو اضافه شد.", "تازه‌وارد از گفتگو خارج شد."])
        line = channel(self.u4).messages.last()
        self.assertIsNone(line.sender)
        self.assertEqual(channel(self.u4).last_message_id, line.pk)

    def test_system_lines_are_never_unread_and_never_deletable(self):
        line = channel(self.s1).messages.filter(kind=MessageKind.SYSTEM).first()
        self.assertEqual(unread(self.s1a, channel(self.s1)), 0)
        with self.assertRaises(PermissionDenied):
            services.delete_message(line, actor=self.s1a)

    def test_a_failed_join_writes_no_line(self):
        with self.assertRaises(ConflictError):
            memberships.add_membership(user=self.s1a, node=self.s1)  # already a member
        self.assertEqual(self.system_lines(self.s1).count("عضو یک به گفتگو اضافه شد."), 1)


class UnreadTests(ChatWorld, TestCase):
    def setUp(self):
        self.build_world()
        self.dm, _ = services.open_direct(actor=self.s1a, other=self.s1b)

    def test_unread_counts_other_peoples_live_messages_after_my_mark(self):
        m1 = services.send_message(self.dm, sender=self.s1a, body="یک")
        services.send_message(self.dm, sender=self.s1a, body="دو")
        m3 = services.send_message(self.dm, sender=self.s1a, body="سه")
        self.assertEqual(unread(self.s1b, self.dm), 3)
        services.mark_read(self.dm, user=self.s1b, up_to=m1.pk)
        self.assertEqual(unread(self.s1b, self.dm), 2)
        services.delete_message(m3, actor=self.s1a)
        self.assertEqual(unread(self.s1b, self.dm), 1)

    def test_my_own_messages_never_count_whatever_my_read_mark_says(self):
        """The query's own definition, independent of send_message moving the sender's mark."""
        from .tests import say

        say(channel(self.s1), self.s1a, "بدون گذر از سرویس")
        self.assertEqual(unread(self.s1a, channel(self.s1)), 0)
        self.assertEqual(unread(self.s1b, channel(self.s1)), 1)

    def test_a_group_member_who_never_opened_the_channel_has_everything_unread(self):
        services.send_message(channel(self.s1), sender=self.s1a, body="یک")
        services.send_message(channel(self.s1), sender=self.u1lead, body="دو")
        self.assertEqual(unread(self.s1b, channel(self.s1)), 2)
        self.assertEqual(unread(self.s1a, channel(self.s1)), 1)

    def test_the_total_sums_everything_listed_for_the_person(self):
        services.send_message(self.dm, sender=self.s1b, body="یک")
        services.send_message(channel(self.s1), sender=self.s1b, body="دو")
        services.send_message(channel(self.root), sender=self.ceo, body="سه")
        services.send_message(channel(self.u2), sender=self.u2m, body="not mine to see")
        access = ChatAccess(self.s1a)
        self.assertEqual(unread_total(access.listed_conversations(), self.s1a), 3)
        self.assertEqual(unread_total(ChatAccess(self.nobody).listed_conversations(), self.nobody), 0)


class ReadMarkTests(ChatWorld, TestCase):
    def setUp(self):
        self.build_world()
        self.dm, _ = services.open_direct(actor=self.s1a, other=self.s1b)
        self.m1 = services.send_message(self.dm, sender=self.s1a, body="یک")
        self.m2 = services.send_message(self.dm, sender=self.s1a, body="دو")

    def test_the_mark_only_moves_forward(self):
        self.assertEqual(services.mark_read(self.dm, user=self.s1b, up_to=self.m2.pk), self.m2.pk)
        self.assertEqual(services.mark_read(self.dm, user=self.s1b, up_to=self.m1.pk), self.m2.pk)

    def test_the_mark_never_passes_the_newest_message(self):
        self.assertEqual(services.mark_read(self.dm, user=self.s1b, up_to=self.m2.pk + 1000), self.m2.pk)

    def test_opening_a_group_channel_for_the_first_time_creates_the_mark(self):
        services.send_message(channel(self.s1), sender=self.s1a, body="یک")
        newest = channel(self.s1).last_message_id
        self.assertEqual(services.mark_read(channel(self.s1), user=self.s1b, up_to=newest), newest)
        self.assertTrue(ConversationParticipant.objects.filter(conversation=channel(self.s1), user=self.s1b).exists())


class DeleteTests(ChatWorld, TestCase):
    def setUp(self):
        self.build_world()
        self.message = services.send_message(channel(self.s1), sender=self.s1a, body="راز")

    def test_the_sender_tombstones_their_own_message(self):
        deleted = services.delete_message(self.message, actor=self.s1a)
        self.assertIsNotNone(deleted.deleted_at)
        self.assertEqual(deleted.deleted_by, self.s1a)
        self.assertTrue(Message.objects.filter(pk=self.message.pk).exists())  # a tombstone, not a delete

    def test_nobody_else_may_delete_it_not_a_lead_not_the_company_lead(self):
        for actor in (self.s1b, self.u1lead, self.ceo):
            with self.assertRaises(PermissionDenied):
                services.delete_message(self.message, actor=actor)
        self.assertIsNone(Message.objects.get(pk=self.message.pk).deleted_at)

    def test_deleting_twice_is_harmless(self):
        first = services.delete_message(self.message, actor=self.s1a).deleted_at
        self.assertEqual(services.delete_message(self.message, actor=self.s1a).deleted_at, first)

    def test_an_archived_channel_is_read_only_for_deletes_too(self):
        tree.archive_node(self.s1)
        with self.assertRaises(ConflictError):
            services.delete_message(self.message, actor=self.s1a)


class MessageApiTests(ChatWorld, OrgApiTestCase):
    def setUp(self):
        super().setUp()
        self.build_world()
        self.dm, _ = services.open_direct(actor=self.s1a, other=self.s1b)

    def url(self, conversation, suffix="messages"):
        return reverse(f"conversation-{suffix}", args=[conversation.pk])

    def send(self, user, conversation, body="سلام"):
        return self.as_(user).post(self.url(conversation), {"body": body}, format="json")

    def bodies(self, response):
        return [row["body"] for row in response.data["results"]]

    def test_sending_is_201_with_the_message(self):
        response = self.send(self.s1a, self.dm, "درود")
        self.assertEqual(response.status_code, 201)
        self.assertEqual((response.data["body"], response.data["sender_name"]), ("درود", self.s1a.full_name))
        self.assertTrue(response.data["is_mine"])
        self.assertTrue(response.data["can_delete"])
        seen_by_other = self.as_(self.s1b).get(self.url(self.dm)).data["results"][-1]
        self.assertEqual((seen_by_other["is_mine"], seen_by_other["can_delete"]), (False, False))

    def test_empty_messages_are_a_persian_400(self):
        response = self.send(self.s1a, self.dm, "  ")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["body"], ["متن پیام نمی‌تواند خالی باشد."])

    def test_nobody_outside_a_dm_can_read_or_write_it_not_even_the_company_lead(self):
        services.send_message(self.dm, sender=self.s1a, body="خصوصی")
        for user in (self.ceo, self.u1lead):
            self.as_(user)
            self.assertEqual(self.client.get(self.url(self.dm)).status_code, 404)
            self.assertEqual(self.client.post(self.url(self.dm), {"body": "x"}, format="json").status_code, 404)
            self.assertEqual(self.client.post(self.url(self.dm, "read"), {"message": 1}, format="json").status_code, 404)
        self.assertEqual(texts(self.dm), ["خصوصی"])

    def test_a_lead_may_read_and_post_in_a_lower_channel(self):
        self.assertEqual(self.send(self.u1lead, channel(self.s1), "از طرف مسئول").status_code, 201)
        self.assertEqual(self.as_(self.s1a).get(self.url(channel(self.s1))).data["results"][-1]["body"], "از طرف مسئول")

    def test_an_archived_channel_answers_409_on_send(self):
        tree.archive_node(self.s1)
        response = self.send(self.s1a, channel(self.s1))
        self.assertEqual((response.status_code, response.data["code"]), (409, "conversation_read_only"))

    def test_the_newest_page_then_scrolling_up_with_before(self):
        for i in range(5):
            services.send_message(self.dm, sender=self.s1a, body=f"{i}")
        self.as_(self.s1b)
        newest = self.client.get(self.url(self.dm), {"limit": 2})
        self.assertEqual((self.bodies(newest), newest.data["has_more"]), (["3", "4"], True))
        older = self.client.get(self.url(self.dm), {"limit": 2, "before": newest.data["results"][0]["id"]})
        self.assertEqual((self.bodies(older), older.data["has_more"]), (["1", "2"], True))
        oldest = self.client.get(self.url(self.dm), {"limit": 2, "before": older.data["results"][0]["id"]})
        self.assertEqual((self.bodies(oldest), oldest.data["has_more"]), (["0"], False))

    def test_polling_with_after_returns_only_newer_messages(self):
        first = services.send_message(self.dm, sender=self.s1a, body="یک")
        self.as_(self.s1b)
        nothing = self.client.get(self.url(self.dm), {"after": first.pk})
        self.assertEqual((nothing.data["results"], nothing.data["has_more"]), ([], False))
        services.send_message(self.dm, sender=self.s1a, body="دو")
        services.send_message(self.dm, sender=self.s1a, body="سه")
        page = self.client.get(self.url(self.dm), {"after": first.pk, "limit": 1})
        self.assertEqual((self.bodies(page), page.data["has_more"]), (["دو"], True))

    def test_bad_cursors_are_a_400(self):
        self.as_(self.s1a)
        for params in ({"before": 1, "after": 1}, {"after": "x"}, {"before": "-1"}, {"limit": "many"}):
            self.assertEqual(self.client.get(self.url(self.dm), params).status_code, 400, params)

    def test_the_limit_is_capped(self):
        with override_settings(CHAT_MAX_PAGE_SIZE=3):
            for i in range(5):
                services.send_message(self.dm, sender=self.s1a, body=f"{i}")
            response = self.as_(self.s1a).get(self.url(self.dm), {"limit": 100})
        self.assertEqual(len(response.data["results"]), 3)

    def test_a_deleted_message_keeps_its_place_but_not_its_words(self):
        message = services.send_message(self.dm, sender=self.s1a, body="پشیمانم")
        response = self.as_(self.s1a).delete(reverse("conversation-message", args=[self.dm.pk, message.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.data["body"], response.data["is_deleted"], response.data["can_delete"]), ("", True, False))
        row = self.as_(self.s1b).get(self.url(self.dm)).data["results"][-1]
        self.assertEqual((row["id"], row["body"], row["is_deleted"]), (message.pk, "", True))
        preview = self.client.get(reverse("conversation-detail", args=[self.dm.pk])).data["last_message"]
        self.assertEqual((preview["preview"], preview["is_deleted"]), ("", True))

    def test_only_the_sender_may_delete_a_message(self):
        message = services.send_message(channel(self.s1), sender=self.s1a, body="من")
        url = reverse("conversation-message", args=[channel(self.s1).pk, message.pk])
        response = self.as_(self.u1lead).delete(url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["detail"], "فقط فرستندهٔ پیام می‌تواند آن را حذف کند.")
        self.assertEqual(self.as_(self.ceo).delete(url).status_code, 403)
        self.assertEqual(self.as_(self.s1a).delete(url).status_code, 200)

    def test_a_message_id_from_another_conversation_is_a_404(self):
        elsewhere = services.send_message(channel(self.s1), sender=self.s1a, body="جای دیگر")
        url = reverse("conversation-message", args=[self.dm.pk, elsewhere.pk])
        self.assertEqual(self.as_(self.s1a).delete(url).status_code, 404)

    def test_read_marks_and_unread_counts_through_the_api(self):
        services.send_message(self.dm, sender=self.s1a, body="یک")
        second = services.send_message(self.dm, sender=self.s1a, body="دو")
        self.as_(self.s1b)
        row = self.client.get(reverse("conversation-detail", args=[self.dm.pk])).data
        self.assertEqual((row["unread_count"], row["my_last_read_message_id"]), (2, None))
        self.assertEqual(row["last_message"]["preview"], "دو")
        response = self.client.post(self.url(self.dm, "read"), {"message": second.pk}, format="json")
        self.assertEqual(response.data, {"last_read_message_id": second.pk})
        row = self.client.get(reverse("conversation-detail", args=[self.dm.pk])).data
        self.assertEqual((row["unread_count"], row["my_last_read_message_id"]), (0, second.pk))
        self.assertEqual(self.client.post(self.url(self.dm, "read"), {}, format="json").status_code, 400)

    def test_the_list_carries_unread_and_previews_without_a_query_per_row(self):
        for other in (self.u2m, self.ceo, self.d2lead):
            dm, _ = services.open_direct(actor=self.s1a, other=other)
            services.send_message(dm, sender=other, body="سلام")
        self.as_(self.s1a)
        with self.assertNumQueries(5):
            rows = self.client.get(reverse("conversation-list")).data["results"]
        self.assertEqual(sum(r["unread_count"] for r in rows if r["kind"] == "DIRECT"), 3)

    @override_settings(RATELIMIT_ENABLE=True, CHAT_SEND_RATELIMIT_RATE="3/m")
    def test_sending_is_rate_limited_per_person_but_reading_is_not(self):
        codes = [self.send(self.s1a, self.dm, f"{i}").status_code for i in range(4)]
        self.assertEqual(codes, [201, 201, 201, 403])
        self.assertEqual(self.as_(self.s1a).get(self.url(self.dm)).status_code, 200)
        self.assertEqual(self.send(self.s1b, self.dm).status_code, 201)


@skipUnlessDBFeature("has_select_for_update")
class MessageConcurrencyTests(Threaded, TransactionTestCase):
    def setUp(self):
        self.root = make_company()
        self.unit = add("UNIT", "واحد", self.root)
        self.people = [person(f"973000000{i}", f"نفر {i}") for i in range(6)]
        for someone in self.people:
            memberships.add_membership(user=someone, node=self.unit)
        self.conversation = Conversation.objects.get(node=self.unit)

    def test_concurrent_senders_leave_the_conversation_pointing_at_its_newest_message(self):
        results = self.run_concurrently(
            lambda i: services.send_message(self.conversation, sender=self.people[i], body=f"{i}").pk, 6
        )
        self.assertTrue(all(kind == "ok" for kind, _ in results), results)
        self.conversation.refresh_from_db()
        newest = self.conversation.messages.order_by("-id").first()
        self.assertEqual(self.conversation.last_message_id, newest.pk)
        self.assertEqual(self.conversation.messages.filter(kind=MessageKind.TEXT).count(), 6)

    def test_concurrent_read_marks_only_ever_move_forward(self):
        sent = [services.send_message(self.conversation, sender=self.people[0], body=f"{i}").pk for i in range(6)]
        reader = self.people[1]
        results = self.run_concurrently(lambda i: services.mark_read(self.conversation, user=reader, up_to=sent[i]), 6)
        self.assertTrue(all(kind == "ok" for kind, _ in results), results)
        mark = ConversationParticipant.objects.get(conversation=self.conversation, user=reader).last_read_message_id
        self.assertEqual(mark, max(sent))
        self.assertEqual(Membership.objects.filter(node=self.unit).count(), 6)
