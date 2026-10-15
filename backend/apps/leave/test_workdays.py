from datetime import date

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import AccessLevel, AccessRoll, User
from apps.documents.test_support import ensure_org, lead_of, member_of

from .models import Holiday, LeaveRequest
from .workdays import jalali_year_bounds, working_days

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "leave-workdays"}}

# 2026-10-14 is a Wednesday, 2026-10-16 a Friday.
WED, THU, FRI, SAT = date(2026, 10, 14), date(2026, 10, 15), date(2026, 10, 16), date(2026, 10, 17)


def person(code, roll=AccessRoll.GUILD, level=AccessLevel.LEVEL_2):
    return User.objects.create_user(
        national_code=code, password="pw-for-tests-123", full_name=f"کاربر {code}", access_roll=roll, access_level=level
    )


class WorkingDayTests(TestCase):
    def test_fridays_and_holidays_are_free(self):
        self.assertEqual(FRI.weekday(), 4)
        self.assertEqual(working_days(WED, SAT), 3)
        Holiday.objects.create(date=SAT, title="تعطیل رسمی")
        self.assertEqual(working_days(WED, SAT), 2)
        self.assertEqual(working_days(FRI, FRI), 0)
        self.assertEqual(working_days(SAT, WED), 0)

    def test_jalali_year_bounds(self):
        self.assertEqual(jalali_year_bounds(1405), (date(2026, 3, 21), date(2027, 3, 20)))


@override_settings(CACHES=LOCMEM, RATELIMIT_ENABLE=False)
class LeaveDaysApiTests(TestCase):
    def setUp(self):
        org = ensure_org()
        self.worker = person("8500000001")
        member_of(self.worker, org.rag)
        self.lead = person("8500000002")
        lead_of(self.lead, org.rag)
        self.hr = person("8500000003", AccessRoll.EMPLOYER, AccessLevel.LEVEL_2)  # manage_personnel

    def api(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def ask(self, start, end):
        return self.api(self.worker).post(
            reverse("leave-list"), {"leave_type": "ANNUAL", "starts_on": start, "ends_on": end}, format="json"
        )

    def test_a_request_counts_working_days(self):
        Holiday.objects.create(date=SAT, title="تعطیل رسمی")
        response = self.ask(WED, SAT)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual((response.data["days"], response.data["calendar_days"]), (2, 4))
        row = self.api(self.lead).get(reverse("leave-list")).data["results"][0]
        self.assertEqual(row["days"], 2)

    def test_a_span_with_no_working_day_is_refused(self):
        Holiday.objects.create(date=SAT, title="تعطیل رسمی")
        response = self.ask(FRI, SAT)
        self.assertEqual(response.status_code, 400)
        self.assertIn("ends_on", response.data)
        self.assertFalse(LeaveRequest.objects.exists())

    def test_the_preview(self):
        Holiday.objects.create(date=THU, title="تاسوعا")
        body = self.api(self.worker).get(reverse("leave-preview"), {"starts_on": WED, "ends_on": SAT}).data
        self.assertEqual((body["days"], body["calendar_days"]), (2, 4))
        self.assertEqual([h["title"] for h in body["holidays"]], ["تاسوعا"])
        bad = self.api(self.worker).get(reverse("leave-preview"), {"starts_on": SAT, "ends_on": WED})
        self.assertEqual(bad.status_code, 400)

    def test_hr_keeps_the_holidays_and_everyone_reads_them(self):
        url = reverse("holiday-list")
        created = self.api(self.hr).post(url, {"date": SAT, "title": "  عيد  "}, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data["title"], "عید")  # normalised
        self.assertEqual(self.api(self.hr).post(url, {"date": SAT, "title": "دوباره"}, format="json").status_code, 409)
        self.assertEqual(self.api(self.worker).post(url, {"date": WED, "title": "x"}, format="json").status_code, 403)
        self.assertEqual(len(self.api(self.worker).get(url).data), 1)
        self.assertEqual(len(self.api(self.worker).get(url, {"year": 1405}).data), 1)
        self.assertEqual(len(self.api(self.worker).get(url, {"year": 1404}).data), 0)
        self.assertEqual(self.api(self.worker).delete(reverse("holiday-detail", args=[created.data["id"]])).status_code, 403)
        self.assertEqual(self.api(self.hr).delete(reverse("holiday-detail", args=[created.data["id"]])).status_code, 204)
