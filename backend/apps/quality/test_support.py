"""Shared fixtures for the quality tests: the sample chart, eight kinds of person, and helpers to report
and to call the API. A record lives at RAG, reported by a plain member of it."""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AccessLevel, AccessRoll, User
from apps.core.constants import DocumentCategory, DocumentGroup
from apps.documents import services as document_services
from apps.documents import test_support
from apps.notifications.models import Notification, NotificationKind
from apps.organization import tree
from apps.organization.access import OrgAccess
from apps.organization.models import Delegation

from . import services  # noqa: F401
from .models import NcSeverity, NcSource, NcStatus, NonConformance, QualityEvent, QualityEventKind

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "veye-quality-tests"}}
_n = [0]


def person(roll=AccessRoll.GUILD, level=AccessLevel.LEVEL_3, name=None, **extra):
    _n[0] += 1
    code = f"95{_n[0]:08d}"
    return User.objects.create_user(
        national_code=code, password="pw-for-tests-123", full_name=name or f"کاربر {code}",
        access_roll=roll, access_level=level, **extra,
    )


@override_settings(CACHES=LOCMEM)
class QualityBase(TestCase):
    """The sample chart (documents/test_support): شرکت › IT › هوش مصنوعی › RAG, LLM; IT › توسعه › Backend.
    A record lives at RAG, reported by a plain member of it."""

    def setUp(self):
        self.org = test_support.ensure_org()
        self.reporter = person(name="گزارش‌دهنده")
        test_support.member_of(self.reporter, self.org.rag)
        self.rag_lead = person(name="مسئول RAG")
        test_support.lead_of(self.rag_lead, self.org.rag)
        self.ai_lead = person(name="مسئول هوش مصنوعی")
        test_support.lead_of(self.ai_lead, self.org.ai)
        self.dev_lead = person(name="مسئول توسعه")  # a sibling unit: unrelated to RAG
        test_support.lead_of(self.dev_lead, self.org.dev)
        self.qm = person(AccessRoll.HEADQUARTERS, name="نمایندهٔ مدیریت")  # manage_quality, no chart place
        self.ceo = person(AccessRoll.EMPLOYER, AccessLevel.LEVEL_1, name="مدیر عامل")
        self.outsider = person(name="بیرونی")
        self.developer = person(is_developer=True, name="توسعه‌دهنده")

    def api(self, user=None) -> APIClient:
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client

    def body(self, **over):
        data = {
            "title": "قطعهٔ معیوب", "description": "قطعه با نقص تحویل شد", "owner_node": self.org.rag.pk,
            "source": NcSource.INTERNAL, "severity": NcSeverity.MAJOR,
        }
        return {**data, **over}

    def make(self, user=None, **over) -> NonConformance:
        response = self.api(user or self.reporter).post(reverse("nonconformance-list"), self.body(**over), format="json")
        assert response.status_code == 201, response.data
        return NonConformance.objects.get(pk=response.data["id"])

    def url(self, name, nc, **kw):
        return reverse(name, args=[nc.pk], **kw)

    def kinds(self, nc=None):
        events = QualityEvent.objects.filter(nc=nc) if nc else QualityEvent.objects.all()
        return list(events.order_by("id").values_list("kind", flat=True))


