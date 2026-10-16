from datetime import date

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import AccessLevel, AccessRoll, User
from apps.core.constants import DocumentCategory, DocumentGroup
from apps.documents import services as document_services
from apps.documents import test_support
from apps.projects.models import Project
from apps.quality.models import NonConformance

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "search-tests"}}


def person(code, roll=AccessRoll.GUILD, level=AccessLevel.LEVEL_2, name=None, **extra):
    return User.objects.create_user(
        national_code=code, password="pw-for-tests-123", full_name=name or f"کاربر {code}", access_roll=roll,
        access_level=level, **extra,
    )


@override_settings(CACHES=LOCMEM, RATELIMIT_ENABLE=False)
class SearchTests(TestCase):
    """Phase 22 ⌘K: one box, every kind of record, each scoped like its own screen."""

    def setUp(self):
        cache.clear()
        self.org = test_support.ensure_org()
        self.lead = person("8400000001", name="مسئول ار‌ای‌جی")
        test_support.lead_of(self.lead, self.org.rag)
        self.stranger = person("8400000002", name="غریبه")
        test_support.member_of(self.stranger, self.org.cash)
        self.doc = document_services.create_document(
            user=self.lead, category=DocumentCategory.INSIDE, title="روش کنترل کیفیت", group=DocumentGroup.PROCEDURE,
            owner_node=self.org.rag,
        )
        self.project = Project.objects.create(
            section=self.org.rag, name="پروژهٔ کیفیت داده", name_key="پروژهٔ کیفیت داده", created_by=self.lead
        )
        self.nc = NonConformance.objects.create(
            title="خطای کیفیت در گزارش", description="شرح", owner_node=self.org.rag, reported_by=self.lead,
            detected_on=date(2026, 10, 1),
        )

    def search(self, user, q):
        client = APIClient()
        client.force_authenticate(user)
        response = client.get(reverse("search"), {"q": q})
        self.assertEqual(response.status_code, 200)
        return {group["type"]: group["items"] for group in response.data["groups"]}

    def test_one_letter_finds_nothing(self):
        self.assertEqual(self.search(self.lead, "ک"), {})

    def test_documents_by_title_and_by_code(self):
        self.assertEqual([i["id"] for i in self.search(self.lead, "کنترل کیفیت")["documents"]], [self.doc.pk])
        hit = self.search(self.lead, self.doc.full_code)["documents"][0]
        self.assertEqual(hit["url"], f"/documents/{self.doc.pk}/edit")
        self.assertIn(self.doc.full_code, hit["title"])

    def test_arabic_letters_find_persian_ones(self):
        # «كيفيت» typed with an Arabic keyboard (ك, ي).
        found = self.search(self.lead, "كيفيت")
        self.assertIn("documents", found)
        self.assertIn("projects", found)
        self.assertIn("nonconformances", found)

    def test_records_are_scoped_like_their_own_screens(self):
        mine = self.search(self.lead, "کیفیت")
        self.assertEqual([i["id"] for i in mine["projects"]], [self.project.pk])
        self.assertEqual([i["id"] for i in mine["nonconformances"]], [self.nc.pk])
        theirs = self.search(self.stranger, "کیفیت")
        self.assertNotIn("projects", theirs)  # neither a member nor a lead above
        self.assertNotIn("nonconformances", theirs)
        self.assertIn("documents", theirs)  # the register is open to everyone

    def test_a_record_id_finds_it(self):
        self.assertEqual([i["id"] for i in self.search(self.lead, self.nc.code)["nonconformances"]], [self.nc.pk])
        self.assertEqual(self.search(self.stranger, self.nc.code).get("nonconformances"), None)

    def test_people_but_not_the_developer_or_the_inactive(self):
        person("8400000003", name="سارا احمدی", is_developer=True)
        retired = person("8400000004", name="سارا رضایی")
        User.objects.filter(pk=retired.pk).update(is_active=False)
        active = person("8400000005", name="سارا محمدي")  # stored with an Arabic ي
        found = self.search(self.lead, "سارا")
        self.assertEqual([i["id"] for i in found["people"]], [active.pk])
        self.assertEqual([i["id"] for i in self.search(self.lead, "محمدی")["people"]], [active.pk])

    def test_org_nodes(self):
        hit = self.search(self.lead, "هوش")["org_nodes"][0]
        self.assertEqual(hit["id"], self.org.ai.pk)
        self.assertEqual(hit["url"], "/organization")  # the chart page takes no node parameter yet

    def test_signed_out_is_refused(self):
        self.assertEqual(APIClient().get(reverse("search"), {"q": "کیفیت"}).status_code, 401)


@override_settings(CACHES=LOCMEM, RATELIMIT_ENABLE=False)
class ListSearchNormalisationTests(TestCase):
    """Phase 22, in passing: the quality and leave lists now match Arabic letters typed into their boxes."""

    def setUp(self):
        self.org = test_support.ensure_org()
        self.manager = person("8400000011", AccessRoll.HEADQUARTERS, AccessLevel.LEVEL_1)  # manage_quality

    def test_non_conformance_titles(self):
        nc = NonConformance.objects.create(
            title="نشتی کیفیت", description="—", owner_node=self.org.rag, reported_by=self.manager, detected_on=date(2026, 10, 1)
        )
        client = APIClient()
        client.force_authenticate(self.manager)
        rows = client.get(reverse("nonconformance-list"), {"q": "كيفيت"}).data["results"]
        self.assertEqual([r["id"] for r in rows], [nc.pk])

    def test_leave_requester_names(self):
        from apps.leave import services as leave

        requester = person("8400000012", name="علي اكبري")  # Arabic ي and ك, as some old records are
        test_support.member_of(requester, self.org.rag)
        leave.request_leave(actor=requester, leave_type="ANNUAL", starts_on=date(2026, 11, 1), ends_on=date(2026, 11, 2))
        hr = person("8400000013", AccessRoll.EMPLOYER, AccessLevel.LEVEL_2)
        client = APIClient()
        client.force_authenticate(hr)
        rows = client.get(reverse("leave-list"), {"q": "علی اکبری"}).data["results"]
        self.assertEqual(len(rows), 1)
