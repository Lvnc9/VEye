"""Announcements (Phase 19): HR and the مدیر عامل publish to the company, a مسئول to their own node and
beneath; who reads what; edit, pin, end date, withdraw; who is told. Chart: documents/test_support's —
IT › هوش مصنوعی › RAG, LLM; IT › توسعه › Backend."""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AccessLevel, AccessRoll, User
from apps.documents import test_support
from apps.notifications.models import Notification, NotificationKind
from apps.organization import tree

from .models import Announcement

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "veye-announce-tests"}}
_n = [0]


def person(roll=AccessRoll.GUILD, level=AccessLevel.LEVEL_3, name=None, **extra):
    _n[0] += 1
    code = f"93{_n[0]:08d}"
    return User.objects.create_user(
        national_code=code, password="pw-for-tests-123", full_name=name or f"کاربر {code}",
        access_roll=roll, access_level=level, **extra,
    )


@override_settings(CACHES=LOCMEM)
class AnnouncementBase(TestCase):
    def setUp(self):
        self.org = test_support.ensure_org()
        self.rag_member = person(name="عضو RAG")
        test_support.member_of(self.rag_member, self.org.rag)
        self.llm_member = person(name="عضو LLM")
        test_support.member_of(self.llm_member, self.org.llm)
        self.dev_member = person(name="عضو Backend")
        test_support.member_of(self.dev_member, self.org.backend)
        self.ai_lead = person(name="مسئول هوش مصنوعی")
        test_support.lead_of(self.ai_lead, self.org.ai)
        self.it_lead = person(name="مسئول IT")
        test_support.lead_of(self.it_lead, self.org.it)
        self.rag_lead = person(name="مسئول RAG")
        test_support.lead_of(self.rag_lead, self.org.rag)
        self.hr = person(AccessRoll.EMPLOYER, AccessLevel.LEVEL_2, name="منابع انسانی")
        self.ceo = person(AccessRoll.EMPLOYER, AccessLevel.LEVEL_1, name="مدیر عامل")
        self.outsider = person(name="بیرونی")
        self.developer = person(is_developer=True, name="توسعه‌دهنده")
        Notification.objects.all().delete()

    def api(self, user=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client

    def publish(self, user, **over):
        body = {"title": "جلسهٔ عمومی", "body": "پنجشنبه ساعت ۱۰", **over}
        return self.api(user).post(reverse("announcement-list"), body, format="json")

    def make(self, user, **over) -> Announcement:
        response = self.publish(user, **over)
        assert response.status_code == 201, response.data
        return Announcement.objects.get(pk=response.data["id"])

    def see(self, user, **params):
        return {r["id"] for r in self.api(user).get(reverse("announcement-list"), params).data["results"]}


class PublishTests(AnnouncementBase):
    def test_who_may_publish_to_the_company(self):
        for who in (self.hr, self.ceo):
            self.assertEqual(self.publish(who).status_code, 201, who.full_name)
        for who in (self.ai_lead, self.it_lead, self.rag_member, self.outsider, self.developer):
            self.assertEqual(self.publish(who).status_code, 403, who.full_name)  # leading a unit is not the company
        self.assertEqual(self.api().post(reverse("announcement-list"), {}, format="json").status_code, 401)

    def test_a_lead_publishes_to_their_node_and_beneath_never_beside_or_above(self):
        self.assertEqual(self.publish(self.ai_lead, audience_node=self.org.ai.pk).status_code, 201)
        self.assertEqual(self.publish(self.ai_lead, audience_node=self.org.rag.pk).status_code, 201)
        for elsewhere in (self.org.dev, self.org.it, self.org.root):
            self.assertEqual(self.publish(self.ai_lead, audience_node=elsewhere.pk).status_code, 403, elsewhere.name)
        self.assertEqual(self.publish(self.hr, audience_node=self.org.dev.pk).status_code, 201)  # HR anywhere
        self.assertEqual(self.publish(self.rag_member, audience_node=self.org.rag.pk).status_code, 403)

    def test_validation(self):
        for bad in ({"title": " "}, {"body": ""}):
            self.assertEqual(self.publish(self.hr, **bad).status_code, 400, bad)
        past = (timezone.localdate() - timedelta(days=1)).isoformat()
        response = self.publish(self.hr, expires_on=past)
        self.assertEqual((response.status_code, response.data["code"]), (409, "expires_in_past"))
        tree.archive_node(self.org.llm)
        response = self.publish(self.hr, audience_node=self.org.llm.pk)
        self.assertEqual((response.status_code, response.data["code"]), (409, "node_archived"))
        self.assertEqual(Announcement.objects.count(), 0)

    def test_publishing_tells_the_audience_never_the_author_nor_the_developer(self):
        self.make(self.hr)
        told = set(Notification.objects.filter(kind=NotificationKind.ANNOUNCEMENT).values_list("recipient_id", flat=True))
        everyone = set(User.objects.filter(is_active=True, is_developer=False).values_list("pk", flat=True))
        self.assertEqual(told, everyone - {self.hr.pk})
        Notification.objects.all().delete()
        self.make(self.ai_lead, audience_node=self.org.ai.pk)
        told = set(Notification.objects.filter(kind=NotificationKind.ANNOUNCEMENT).values_list("recipient_id", flat=True))
        # placed in AI or beneath (the RAG and LLM members and the RAG lead), and the lead above (IT)
        self.assertEqual(told, {self.rag_member.pk, self.llm_member.pk, self.rag_lead.pk, self.it_lead.pk})


class ReadTests(AnnouncementBase):
    def setUp(self):
        super().setUp()
        self.company = self.make(self.hr, title="عمومی")
        self.ai = self.make(self.ai_lead, title="هوش مصنوعی", audience_node=self.org.ai.pk)
        self.rag = self.make(self.rag_lead, title="RAG", audience_node=self.org.rag.pk)

    def test_who_reads_what(self):
        everything = {self.company.pk, self.ai.pk, self.rag.pk}
        self.assertEqual(self.see(self.rag_member), everything)  # placed beneath both node audiences
        self.assertEqual(self.see(self.llm_member), {self.company.pk, self.ai.pk})  # not RAG's
        self.assertEqual(self.see(self.dev_member), {self.company.pk})
        self.assertEqual(self.see(self.it_lead), everything)  # leads above
        self.assertEqual(self.see(self.ai_lead), everything)
        self.assertEqual(self.see(self.hr), everything)
        self.assertEqual(self.see(self.outsider), {self.company.pk})
        self.assertEqual(self.api(self.dev_member).get(reverse("announcement-detail", args=[self.ai.pk])).status_code, 404)

    def test_pinned_first_then_newest(self):
        self.api(self.hr).patch(reverse("announcement-detail", args=[self.company.pk]), {"pinned": True}, format="json")
        rows = [r["id"] for r in self.api(self.rag_member).get(reverse("announcement-list")).data["results"]]
        self.assertEqual(rows, [self.company.pk, self.rag.pk, self.ai.pk])

    def test_an_expired_one_moves_to_the_archive(self):
        Announcement.objects.filter(pk=self.ai.pk).update(expires_on=timezone.localdate() - timedelta(days=1))
        self.assertNotIn(self.ai.pk, self.see(self.rag_member))
        self.assertEqual(self.see(self.rag_member, archive=1), {self.ai.pk})
        self.assertTrue(self.api(self.rag_member).get(reverse("announcement-detail", args=[self.ai.pk])).data["is_expired"])

    def test_a_withdrawn_one_is_seen_only_by_those_who_manage_it(self):
        self.api(self.ai_lead).post(reverse("announcement-withdraw", args=[self.ai.pk]))
        self.assertNotIn(self.ai.pk, self.see(self.rag_member) | self.see(self.rag_member, archive=1))
        self.assertEqual(self.api(self.rag_member).get(reverse("announcement-detail", args=[self.ai.pk])).status_code, 404)
        for manager in (self.ai_lead, self.it_lead, self.hr):
            self.assertIn(self.ai.pk, self.see(manager, archive=1), manager.full_name)
        self.assertNotIn(self.ai.pk, self.see(self.ai_lead))  # not in the current list


class ManageTests(AnnouncementBase):
    def setUp(self):
        super().setUp()
        self.ai = self.make(self.ai_lead, audience_node=self.org.ai.pk)

    def patch(self, user, **body):
        return self.api(user).patch(reverse("announcement-detail", args=[self.ai.pk]), body, format="json")

    def test_who_may_edit_and_withdraw(self):
        self.assertEqual(self.patch(self.rag_lead, title="x").status_code, 403)  # reads it, does not manage it
        self.assertEqual(self.patch(self.rag_member, title="x").status_code, 403)
        for manager in (self.ai_lead, self.it_lead, self.hr):
            self.assertEqual(self.patch(manager, title=f"عنوان {manager.pk}").status_code, 200, manager.full_name)
        self.assertEqual(self.api(self.rag_lead).post(reverse("announcement-withdraw", args=[self.ai.pk])).status_code, 403)

    def test_every_flag_agrees_with_the_endpoint(self):
        for viewer in (self.ai_lead, self.it_lead, self.hr, self.rag_lead, self.rag_member):
            offered = self.api(viewer).get(reverse("announcement-detail", args=[self.ai.pk])).data["can_manage"]
            worked = self.patch(viewer, pinned=not Announcement.objects.get(pk=self.ai.pk).pinned).status_code == 200
            self.assertEqual(offered, worked, viewer.full_name)

    def test_changing_the_words_marks_it_edited_but_a_pin_does_not(self):
        self.assertIsNone(self.patch(self.ai_lead, pinned=True).data["edited_at"])
        self.assertIsNotNone(self.patch(self.ai_lead, body="متن تازه").data["edited_at"])

    def test_the_audience_is_fixed_and_nobody_is_told_again(self):
        Notification.objects.all().delete()
        response = self.patch(self.hr, audience_node=self.org.dev.pk, title="تازه")
        self.assertEqual(response.data["audience_node"], self.org.ai.pk)  # ignored, not moved
        self.assertEqual(Notification.objects.count(), 0)

    def test_an_end_date_in_the_past_is_refused_and_clearing_it_is_fine(self):
        past = (timezone.localdate() - timedelta(days=2)).isoformat()
        self.assertEqual(self.patch(self.ai_lead, expires_on=past).data["code"], "expires_in_past")
        self.assertIsNone(self.patch(self.ai_lead, expires_on=None).data["expires_on"])

    def test_withdrawing_is_final_and_freezes_it(self):
        response = self.api(self.ai_lead).post(reverse("announcement-withdraw", args=[self.ai.pk]))
        self.assertEqual((response.status_code, response.data["is_withdrawn"], response.data["can_manage"]), (200, True, False))
        self.assertEqual(self.api(self.ai_lead).post(reverse("announcement-withdraw", args=[self.ai.pk])).data["code"], "withdrawn")
        self.assertEqual(self.patch(self.ai_lead, title="x").data["code"], "withdrawn")


class GuardTests(AnnouncementBase):
    def test_an_author_cannot_be_deleted_and_an_announced_node_says_so(self):
        lone_hr = person(AccessRoll.EMPLOYER, AccessLevel.LEVEL_2)
        self.make(lone_hr, audience_node=self.org.llm.pk)
        response = self.api(self.ceo).delete(reverse("personnel-detail", args=[lone_hr.pk]))
        self.assertEqual((response.status_code, response.data["code"]), (409, "user_has_announcements"))
        response = self.api(self.ceo).delete(reverse("org-node-detail", args=[self.org.llm.pk]))
        self.assertEqual((response.status_code, response.data["announcements"]), (409, 1))
