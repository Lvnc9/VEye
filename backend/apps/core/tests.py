from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import AccessLevel, AccessRoll
from apps.accounts.tests import LOCMEM_CACHE, make_user

from .exceptions import NOT_FOUND_MESSAGE


@override_settings(CACHES=LOCMEM_CACHE, RATELIMIT_ENABLE=False)
class NotFoundIsPersianTests(TestCase):
    """A missing object must never surface Django's English «No X matches the given query.»"""

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=False)
        self.client.force_authenticate(make_user("9500000001", AccessRoll.EMPLOYER, AccessLevel.LEVEL_1))

    def test_a_missing_object_is_answered_in_persian(self):
        for name, args in (("org-node-detail", [999999999]), ("org-membership-detail", [999999999]), ("personnel-detail", [999999999])):
            with self.subTest(route=name):
                response = self.client.get(reverse(name, args=args))
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.data["detail"], NOT_FOUND_MESSAGE)
                self.assertNotIn("matches the given query", response.content.decode())

    def test_a_bare_http404_is_answered_in_persian_too(self):
        response = self.client.get(reverse("org-company-logo"))  # no company yet: NotFound raised by the view
        self.assertEqual(response.status_code, 404)
        self.assertNotRegex(response.data["detail"], r"[A-Za-z]")
