from datetime import date

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AccessLevel, AccessRoll, User
from apps.documents.test_support import ensure_org, lead_of, member_of

from .balances import Ledger, days_by_year
from .models import LeaveEntitlement, LeavePolicy, LeaveRequest, LeaveStatus, LeaveType
from .workdays import HolidayCache

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "leave-balances"}}


def person(code, roll=AccessRoll.GUILD, level=AccessLevel.LEVEL_2):
    return User.objects.create_user(
        national_code=code, password="pw-for-tests-123", full_name=f"کاربر {code}", access_roll=roll, access_level=level
    )


def leave(user, start, end, status=LeaveStatus.APPROVED, leave_type=LeaveType.ANNUAL, node=None):
    decided = timezone.now() if status in (LeaveStatus.APPROVED, LeaveStatus.REJECTED) else None
    return LeaveRequest.objects.create(
        requester=user, starts_on=start, ends_on=end, status=status, leave_type=leave_type, decided_at=decided, node=node
    )


# 2026-10-14 Wed … 2026-10-17 Sat (Friday 16th free): three working days, all in Jalali 1405.
WED, SAT = date(2026, 10, 14), date(2026, 10, 17)


class LedgerTests(TestCase):
    def setUp(self):
        LeavePolicy.objects.create(pk=1, annual_days=26, carry_max=9, start_year=1405)
        self.user = person("8600000001")

    def balance(self, year):
        return Ledger(self.user).balance(year)

    def test_a_fresh_year(self):
        b = self.balance(1405)
        self.assertEqual((b.entitlement, b.carried, b.used, b.pending, b.remaining), (26, 0, 0, 0, 26))

    def test_only_approved_annual_leave_is_used_and_pending_is_shown_apart(self):
        leave(self.user, WED, SAT)
        leave(self.user, date(2026, 11, 1), date(2026, 11, 2), status=LeaveStatus.PENDING)
        leave(self.user, date(2026, 11, 8), date(2026, 11, 9), leave_type=LeaveType.SICK)
        leave(self.user, date(2026, 11, 15), date(2026, 11, 16), status=LeaveStatus.REJECTED)
        b = self.balance(1405)
        self.assertEqual((b.used, b.pending, b.remaining), (3, 2, 23))

    def test_unused_days_carry_over_up_to_the_cap(self):
        leave(self.user, date(2026, 4, 4), date(2026, 4, 15))  # 1405: 12 days, minus Fridays 10 and … counted below
        used = Ledger(self.user).used[1405]
        remaining = 26 - used
        self.assertEqual(self.balance(1406).carried, min(9, remaining))
        self.assertEqual(self.balance(1406).remaining, 26 + min(9, remaining))

    def test_a_small_remainder_carries_whole_and_an_overdraw_carries_nothing(self):
        LeaveEntitlement.objects.create(user=self.user, year=1405, days=5)  # e.g. an opening balance
        leave(self.user, WED, SAT)  # 3 days
        self.assertEqual(self.balance(1406).carried, 2)
        LeaveEntitlement.objects.filter(user=self.user, year=1405).update(days=1)
        self.assertEqual(self.balance(1405).remaining, -2)
        self.assertEqual(self.balance(1406).carried, 0)

    def test_a_request_across_nowruz_is_split_by_year(self):
        # 2027-03-18 Thu, 19 Fri (free), 20 Sat = 1405; 21 Sun, 22, 23 = 1406.
        split = days_by_year(date(2027, 3, 18), date(2027, 3, 23), HolidayCache())
        self.assertEqual(split, {1405: 2, 1406: 3})
        leave(self.user, date(2027, 3, 18), date(2027, 3, 23))
        self.assertEqual(self.balance(1405).used, 2)
        self.assertEqual(self.balance(1406).used, 3)

    def test_years_before_the_start_are_not_tracked(self):
        self.assertIsNone(self.balance(1404))

    def test_an_entitlement_replaces_the_policy(self):
        LeaveEntitlement.objects.create(user=self.user, year=1405, days=30)
        self.assertEqual(self.balance(1405).entitlement, 30)
        self.assertEqual(self.balance(1406).entitlement, 26)


@override_settings(CACHES=LOCMEM, RATELIMIT_ENABLE=False)
class BalanceApiTests(TestCase):
    def setUp(self):
        LeavePolicy.objects.create(pk=1, annual_days=26, carry_max=9, start_year=1405)
        org = ensure_org()
        self.worker = person("8600000011")
        member_of(self.worker, org.rag, is_primary=True)
        self.lead = person("8600000012")
        lead_of(self.lead, org.rag)
        self.outsider = person("8600000013")
        member_of(self.outsider, org.cash)
        self.hr = person("8600000014", AccessRoll.EMPLOYER, AccessLevel.LEVEL_2)

    def api(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_my_balance(self):
        body = self.api(self.worker).get(reverse("leave-balance"), {"year": 1405}).data
        self.assertTrue(body["tracked"])
        self.assertEqual(body["balance"]["remaining"], 26)
        self.assertFalse(self.api(self.worker).get(reverse("leave-balance"), {"year": 1404}).data["tracked"])

    def test_whose_balance_one_may_read(self):
        url = reverse("leave-balance")
        self.assertEqual(self.api(self.lead).get(url, {"user": self.worker.pk}).status_code, 200)
        self.assertEqual(self.api(self.hr).get(url, {"user": self.worker.pk}).status_code, 200)
        self.assertEqual(self.api(self.outsider).get(url, {"user": self.worker.pk}).status_code, 404)
        self.assertEqual(self.api(self.worker).get(url, {"user": self.lead.pk}).status_code, 404)

    def test_hr_lists_everyones_balance_and_sets_entitlements(self):
        self.assertEqual(self.api(self.lead).get(reverse("leave-balances")).status_code, 403)
        rows = self.api(self.hr).get(reverse("leave-balances"), {"year": 1405}).data["results"]
        self.assertIn(self.worker.pk, [r["user"]["id"] for r in rows])
        url = reverse("leave-entitlements")
        body = {"user": self.worker.pk, "year": 1405, "days": 30}
        self.assertEqual(self.api(self.lead).put(url, body, format="json").status_code, 403)
        response = self.api(self.hr).put(url, body, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["balance"]["entitlement"], 30)
        cleared = self.api(self.hr).put(url, {**body, "days": None}, format="json")
        self.assertEqual(cleared.data["balance"]["entitlement"], 26)

    def test_the_decider_is_warned_about_an_overdraw(self):
        LeaveEntitlement.objects.create(user=self.worker, year=1405, days=2)
        big = leave(self.worker, WED, SAT, status=LeaveStatus.PENDING, node=ensure_org().rag)  # 3 working days > 2
        rows = {r["id"]: r for r in self.api(self.lead).get(reverse("leave-list")).data["results"]}
        self.assertEqual(rows[big.pk]["balance_warning"], {"year": 1405, "requested": 3, "remaining": 2})
        LeaveEntitlement.objects.filter(user=self.worker).update(days=3)
        rows = {r["id"]: r for r in self.api(self.lead).get(reverse("leave-list")).data["results"]}
        self.assertIsNone(rows[big.pk]["balance_warning"])

    def test_the_preview_shows_what_would_be_left(self):
        LeaveEntitlement.objects.create(user=self.worker, year=1405, days=2)
        body = self.api(self.worker).get(reverse("leave-preview"), {"starts_on": WED, "ends_on": SAT}).data
        self.assertEqual(body["balance"], [{"year": 1405, "requested": 3, "remaining": 2, "exceeds": True}])
        sick = self.api(self.worker).get(reverse("leave-preview"), {"starts_on": WED, "ends_on": SAT, "leave_type": "SICK"})
        self.assertEqual(sick.data["balance"], [])

    def test_the_policy(self):
        url = reverse("leave-policy")
        self.assertEqual(self.api(self.worker).get(url).data["annual_days"], 26)
        self.assertEqual(self.api(self.worker).patch(url, {"annual_days": 30}, format="json").status_code, 403)
        self.assertEqual(self.api(self.hr).patch(url, {"annual_days": 30, "carry_max": 5}, format="json").data["carry_max"], 5)
        self.assertEqual(self.api(self.hr).patch(url, {"annual_days": 61}, format="json").status_code, 400)

    def test_the_policy_starts_in_the_current_year_when_first_read(self):
        from .workdays import jalali_year_of

        LeavePolicy.objects.all().delete()
        self.assertEqual(LeavePolicy.current().start_year, jalali_year_of(timezone.localdate()))
