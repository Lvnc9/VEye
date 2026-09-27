"""First-run setup — bootstrap (the developer account), start (the company), complete, status, the
wizard's bookmark. Phase 10, ADR-010: no مدیر عامل is minted here at all; the developer runs every
step and the مدیر عامل is registered afterwards as ordinary personnel."""
from unittest import mock

from django.conf import settings
from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import AccessLevel, AccessRoll, Capability, User
from apps.accounts.tests import LOCMEM_CACHE, make_user
from apps.chat.models import Conversation
from apps.core.exceptions import ConflictError

from . import bootstrap, memberships, services, tree
from .models import Company, Membership, OrgNode, OrgNodeKind, SetupStep
from .setup_views import DEFAULT_COMPANY_NAME
from .tests import Threaded

STRONG = "Qz7-vector-maple-93"

DEV = {
    "full_name": "  علی   رضايي ",
    "national_code": "۱۲۳۴۵۶۷۸۹۰",
    "mobile_phone": "۰۹۱۲ ۱۱۱ ۲۲۳۳",
    "password": STRONG,
}


def payload(**overrides):
    body = dict(DEV)
    body.update(overrides)
    return body


@override_settings(CACHES=LOCMEM_CACHE, RATELIMIT_ENABLE=False)
class SetupCase(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=False)
        self.url = reverse("setup-bootstrap")

    def post(self, body=None, client=None, **headers):
        return (client or self.client).post(self.url, payload() if body is None else body, format="json", **headers)

    def anon(self):
        return APIClient(enforce_csrf_checks=False)

    def nothing_was_created(self):
        self.assertFalse(Company.objects.exists())
        self.assertFalse(OrgNode.objects.exists())
        self.assertFalse(Membership.objects.exists())


class SetupStatusTests(SetupCase):
    def status(self, client=None):
        return (client or self.client).get(reverse("setup-status"))

    def test_a_fresh_database_reports_nothing_yet(self):
        response = self.status()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {"developer_exists": False, "company_exists": False, "completed": False, "step": None, "has_root_lead": False},
        )

    def test_it_is_public_and_ignores_a_bad_session_cookie(self):
        self.client.cookies["access_token"] = "garbage.token.value"
        self.assertEqual(self.status().status_code, 200)

    def test_it_answers_exactly_five_keys_and_no_store(self):
        response = self.status()
        self.assertEqual(
            set(response.data), {"developer_exists", "company_exists", "completed", "step", "has_root_lead"}
        )
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_after_bootstrap_it_reports_the_developer_and_nothing_else(self):
        self.post()
        data = self.status().data
        self.assertEqual(
            data,
            {"developer_exists": True, "company_exists": False, "completed": False, "step": None, "has_root_lead": False},
        )

    def test_after_start_it_reports_the_company_and_step(self):
        self.post()
        self.client.post(reverse("setup-start"))
        data = self.status().data
        self.assertEqual(
            data,
            {
                "developer_exists": True,
                "company_exists": True,
                "completed": False,
                "step": SetupStep.DOMAINS,
                "has_root_lead": False,
            },
        )


class NoTokenTests(SetupCase):
    """The setup token is gone (owner, 2026-09-25): a fresh database is bootstrapped from the form
    alone."""

    def test_a_fresh_database_is_bootstrapped_with_no_token_at_all(self):
        self.assertEqual(self.post().status_code, 201)
        self.assertTrue(User.objects.filter(is_developer=True).exists())

    def test_a_leftover_token_header_or_setting_changes_nothing(self):
        with override_settings(SETUP_TOKEN="whatever"):
            response = self.post(HTTP_X_VEYE_SETUP_TOKEN="wrong")
        self.assertEqual(response.status_code, 201)

    @override_settings(RATELIMIT_ENABLE=True, SETUP_RATELIMIT_RATE="3/m")
    def test_every_attempt_counts_against_the_per_ip_limit(self):
        codes = [self.post(client=self.anon()).status_code for _ in range(5)]
        self.assertEqual(codes, [201, 409, 409, 403, 403])  # the 403s are the limiter


class DeveloperBootstrapTests(SetupCase):
    def test_it_creates_the_developer_with_no_membership_and_no_company(self):
        response = self.post()
        self.assertEqual(response.status_code, 201, response.data)

        user = User.objects.get()
        self.assertTrue(user.is_developer)
        self.assertEqual((user.access_roll, user.access_level), (AccessRoll.GUILD, AccessLevel.LEVEL_3))
        self.assertEqual(user.title, "توسعه‌دهنده")
        self.assertEqual(user.full_name, "علی رضایی")
        self.assertEqual(user.national_code, "1234567890")  # Persian digits -> ASCII
        self.assertEqual(user.mobile_phone, "09121112233")
        self.assertTrue(user.check_password(STRONG))
        self.assertFalse(user.is_superuser or user.is_staff)  # not a Django-admin concept
        self.nothing_was_created()  # no Company, no OrgNode, no Membership

    def test_the_developer_holds_exactly_the_developer_capabilities(self):
        self.post()
        user = User.objects.get()
        self.assertEqual(
            user.capabilities,
            frozenset({Capability.MANAGE_ORGANIZATION, Capability.MANAGE_MEMBERSHIP, Capability.MANAGE_PERSONNEL}),
        )
        self.assertNotIn(Capability.CREATE_DOCUMENT, user.capabilities)
        self.assertNotIn(Capability.CREATE_PROJECT, user.capabilities)

    def test_the_new_developer_is_signed_in_and_the_wizard_can_continue_under_that_session(self):
        response = self.post()
        for name in (settings.JWT_ACCESS_COOKIE_NAME, settings.JWT_REFRESH_COOKIE_NAME):
            self.assertTrue(response.cookies[name]["httponly"], name)
        me = self.client.get(reverse("auth-me"))  # the cookie jar carries the session
        self.assertEqual(me.status_code, 200)
        self.assertTrue(me.data["is_developer"])
        # ...and setup/start/ works with it, no other endpoint involved.
        started = self.client.post(reverse("setup-start"))
        self.assertEqual(started.status_code, 201, started.data)

    def test_the_response_never_contains_the_password_or_its_hash(self):
        response = self.post()
        text = response.content.decode()
        self.assertNotIn(STRONG, text)
        self.assertNotIn(User.objects.get().password, text)
        self.assertNotIn("password", response.data["user"])
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_a_second_bootstrap_is_a_409_and_changes_nothing(self):
        self.post()
        again = self.post(payload(national_code="9999999999"), client=self.anon())
        self.assertEqual((again.status_code, again.data["code"]), (409, "developer_exists"))
        self.assertEqual(User.objects.count(), 1)
        self.nothing_was_created()

    def test_a_duplicate_national_code_is_a_409_with_everything_rolled_back(self):
        make_user("1234567890", AccessRoll.GUILD, AccessLevel.LEVEL_3)
        response = self.post()
        self.assertEqual((response.status_code, response.data["code"]), (409, "national_code_exists"))
        self.nothing_was_created()
        self.assertEqual(User.objects.count(), 1)
        self.assertFalse(User.objects.filter(is_developer=True).exists())

    def test_a_national_code_taken_after_the_pre_check_is_still_a_409(self):
        """The window between "nobody has this code" and the insert: someone else (personnel
        registration, another request) takes it. The unique constraint must give the same 409 and
        roll everything in the transaction back with it — simulated deterministically."""
        real_create_user = User.objects.create_user

        def take_the_code_first(*args, **kwargs):
            real_create_user("1234567890", "x", full_name="رقیب", access_roll="GUILD", access_level="L3")
            return real_create_user(*args, **kwargs)

        with mock.patch.object(User.objects, "create_user", side_effect=take_the_code_first):
            response = self.post()
        self.assertEqual((response.status_code, response.data["code"]), (409, "national_code_exists"))
        self.nothing_was_created()
        self.assertEqual(User.objects.count(), 0)  # "رقیب" rolled back too — same transaction

    def test_bad_payloads_are_400s_and_create_nothing(self):
        cases = {
            "no full name": {k: v for k, v in DEV.items() if k != "full_name"},
            "no national code": {k: v for k, v in DEV.items() if k != "national_code"},
            "no password": {k: v for k, v in DEV.items() if k != "password"},
            "blank national code": payload(national_code="  "),
        }
        for label, body in cases.items():
            with self.subTest(label):
                self.assertEqual(self.post(body, client=self.anon()).status_code, 400)
        self.nothing_was_created()

    def test_the_password_must_pass_djangos_validators_in_persian(self):
        for label, password in {"short": "Ab1-x", "all digits": "839201746512", "common": "password123",
                                "like the name": "1234567890"}.items():
            with self.subTest(label):
                response = self.post(payload(password=password), client=self.anon())
                self.assertEqual(response.status_code, 400)
                self.assertIn("password", response.data)
        self.nothing_was_created()

    def test_a_password_with_leading_or_trailing_spaces_is_kept_exactly(self):
        self.post(payload(password="  " + STRONG + "  "))
        self.assertTrue(User.objects.get().check_password("  " + STRONG + "  "))


class DeveloperExistsTests(SetupCase):
    """Once a developer exists, the anonymous form is closed: that person signs in and continues."""

    def setUp(self):
        super().setUp()
        self.post()  # self.client is now the developer's own session

    def test_the_anonymous_form_is_a_persian_409_and_creates_nothing(self):
        response = self.post(client=self.anon())
        self.assertEqual((response.status_code, response.data["code"]), (409, "developer_exists"))
        self.assertIn("توسعه‌دهنده", str(response.data["detail"]))
        self.assertEqual(User.objects.filter(is_developer=True).count(), 1)
        self.assertNotIn(settings.JWT_ACCESS_COOKIE_NAME, response.cookies)


class SetupStartTests(SetupCase):
    """`POST /setup/start/`: the developer's one button. No membership is ever written here."""

    def setUp(self):
        super().setUp()
        self.start_url = reverse("setup-start")
        self.post()  # self.client is now the developer's own session

    def start(self, client=None, body=None):
        return (client or self.client).post(self.start_url, body or {}, format="json")

    def test_the_developer_starts_setup_with_one_press(self):
        response = self.start()
        self.assertEqual(response.status_code, 201, response.data)
        company = Company.objects.get()
        self.assertEqual((company.root.name, company.setup_step), (DEFAULT_COMPANY_NAME, SetupStep.DOMAINS))
        self.assertEqual(company.root.kind, OrgNodeKind.COMPANY)
        self.assertFalse(Membership.objects.exists())  # the developer never sits in the chart
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_a_company_name_can_be_given(self):
        self.assertEqual(self.start(body={"company_name": "  وپورویر "}).status_code, 201)
        self.assertEqual(Company.objects.get().root.name, "وپورویر")

    def test_it_needs_a_session(self):
        self.assertEqual(self.start(client=self.anon()).status_code, 401)
        self.nothing_was_created()

    def test_only_the_developer_may_start_and_it_is_a_persian_403(self):
        for user in (
            make_user("2000000002", AccessRoll.EMPLOYER, AccessLevel.LEVEL_1),
            make_user("2000000003", AccessRoll.GUILD, AccessLevel.LEVEL_3),
            make_user("2000000004", AccessRoll.HEADQUARTERS, AccessLevel.LEVEL_1),
        ):
            with self.subTest(user=user.national_code):
                client = self.anon()
                client.force_authenticate(user)
                response = self.start(client=client)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(str(response.data["detail"]), "راه‌اندازی شرکت را فقط توسعه‌دهنده می‌تواند شروع کند.")
        self.nothing_was_created()

    def test_a_second_start_is_a_409_and_the_anonymous_form_stays_shut_too(self):
        self.assertEqual(self.start().status_code, 201)
        again = self.start()
        self.assertEqual((again.status_code, again.data["code"]), (409, "already_bootstrapped"))
        self.assertEqual(self.post(client=self.anon()).status_code, 409)
        self.assertEqual(Company.objects.count(), 1)

    def test_a_failure_after_the_root_is_created_leaves_no_half_started_company(self):
        """The root node is written before the Company row. If the second write fails the first
        must vanish with it — the property the single transaction exists for."""
        with mock.patch.object(Company.objects, "create", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                bootstrap.start_company(company_name="شرکت")
        self.assertFalse(OrgNode.objects.exists())
        self.assertFalse(Company.objects.exists())


class CompleteTests(SetupCase):
    def setUp(self):
        super().setUp()
        self.post()
        self.client.post(reverse("setup-start"))
        self.url_complete = reverse("setup-complete")
        self.company = Company.objects.get()
        self.developer = User.objects.get(is_developer=True)

    def place_a_lead(self, node=None, code="3000000009"):
        boss = make_user(code, AccessRoll.EMPLOYER, AccessLevel.LEVEL_1)
        memberships.add_membership(user=boss, node=node or self.company.root, is_lead=True, is_primary=True)
        return boss

    def as_(self, user):
        client = self.anon()
        client.force_authenticate(user)
        return client

    def test_it_needs_a_session(self):
        self.assertEqual(self.anon().post(self.url_complete).status_code, 401)

    def test_it_needs_the_developer_not_just_manage_organization(self):
        boss = self.place_a_lead()  # holds manage_organization too, but is not the developer
        response = self.as_(boss).post(self.url_complete)
        self.assertEqual(response.status_code, 403)
        self.assertIsNone(Company.objects.get().setup_completed_at)

    def test_it_is_409_root_lead_missing_until_someone_leads_the_root(self):
        response = self.client.post(self.url_complete)
        self.assertEqual((response.status_code, response.data["code"]), (409, "root_lead_missing"))
        self.assertIsNone(Company.objects.get().setup_completed_at)

    def test_a_lead_on_a_child_node_does_not_count_only_the_root_does(self):
        domain = tree.create_node(kind="DOMAIN", name="حوزه", parent=self.company.root)
        self.place_a_lead(node=domain)
        response = self.client.post(self.url_complete)
        self.assertEqual((response.status_code, response.data["code"]), (409, "root_lead_missing"))

    def test_a_deactivated_lead_does_not_count(self):
        boss = self.place_a_lead()
        boss.is_active = False
        boss.save(update_fields=["is_active"])
        response = self.client.post(self.url_complete)
        self.assertEqual((response.status_code, response.data["code"]), (409, "root_lead_missing"))

    def test_the_developer_completes_setup_once_a_root_lead_exists(self):
        self.place_a_lead()
        response = self.client.post(self.url_complete)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            response.data,
            {
                "developer_exists": True,
                "company_exists": True,
                "completed": True,
                "step": SetupStep.DONE,
                "has_root_lead": True,
            },
        )
        company = Company.objects.get()
        self.assertEqual(company.setup_step, SetupStep.DONE)
        self.assertIsNotNone(company.setup_completed_at)

        again = self.client.post(self.url_complete)
        self.assertEqual((again.status_code, again.data["code"]), (409, "already_completed"))
        self.assertEqual(Company.objects.get().setup_completed_at, company.setup_completed_at)  # untouched

    def test_it_needs_no_further_structure_once_a_lead_exists(self):
        self.place_a_lead()
        self.assertEqual(OrgNode.objects.count(), 1)  # just the company root
        self.assertEqual(self.client.post(self.url_complete).status_code, 200)

    def test_bootstrap_and_start_stay_dead_after_completion(self):
        self.place_a_lead()
        self.client.post(self.url_complete)
        self.assertEqual(self.post(payload(national_code="5555555555"), client=self.anon()).status_code, 409)
        self.assertEqual(self.client.post(reverse("setup-start")).status_code, 409)


class CompleteWithoutCompanyTests(SetupCase):
    def test_it_is_a_404_before_a_company_exists(self):
        self.post()  # the developer only, no company yet
        self.assertEqual(self.client.post(reverse("setup-complete")).status_code, 404)

    def test_it_is_a_404_if_the_company_was_removed(self):
        self.post()
        self.client.post(reverse("setup-start"))
        Conversation.objects.all().delete()  # every node's channel PROTECTs it
        Company.objects.all().delete()
        OrgNode.objects.all().delete()
        self.assertEqual(self.client.post(reverse("setup-complete")).status_code, 404)


class DeveloperExclusionTests(SetupCase):
    """The developer never sits in the chart: `/org/people/` (:289) never lists it, and placing it
    is a Persian 400 (`MembershipCreateSerializer.validate_user`)."""

    def setUp(self):
        super().setUp()
        self.post()
        self.developer = User.objects.get(is_developer=True)
        self.client.post(reverse("setup-start"))
        self.company = Company.objects.get()
        self.boss = make_user("3100000001", AccessRoll.EMPLOYER, AccessLevel.LEVEL_1)
        memberships.add_membership(user=self.boss, node=self.company.root, is_lead=True, is_primary=True)

    def as_boss(self):
        client = self.anon()
        client.force_authenticate(self.boss)
        return client

    def test_the_developer_never_appears_in_org_people(self):
        response = self.as_boss().get(reverse("org-people"))
        self.assertEqual(response.status_code, 200)
        ids = [row["id"] for row in response.data["results"]]
        self.assertNotIn(self.developer.pk, ids)

    def test_the_developer_never_appears_as_unassigned_either(self):
        response = self.as_boss().get(reverse("org-people"), {"unassigned": "1"})
        ids = [row["id"] for row in response.data["results"]]
        self.assertNotIn(self.developer.pk, ids)

    def test_the_developer_cannot_be_placed_in_the_chart(self):
        response = self.as_boss().post(
            reverse("org-membership-list"),
            {"user": self.developer.pk, "node": self.company.root_id},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("توسعه", str(response.data["user"][0]))  # ZWNJ makes the full word repr-unstable
        self.assertFalse(Membership.objects.filter(user=self.developer).exists())


class BookmarkTests(SetupCase):
    """`Company.setup_step` follows the last thing written, in the same transaction."""

    def setUp(self):
        super().setUp()
        self.post()
        self.client.post(reverse("setup-start"))
        self.company = lambda: Company.objects.get()
        self.root = Company.objects.get().root

    def test_each_kind_of_write_moves_the_bookmark_to_its_step(self):
        domain = tree.create_node(kind="DOMAIN", name="ح", parent=self.root)
        self.assertEqual(self.company().setup_step, SetupStep.DOMAINS)
        unit = tree.create_node(kind="UNIT", name="و", parent=domain)
        self.assertEqual(self.company().setup_step, SetupStep.UNITS)
        tree.create_node(kind="SECTION", name="ب", parent=unit)
        self.assertEqual(self.company().setup_step, SetupStep.SECTIONS)
        memberships.add_membership(user=make_user("4000000001", AccessRoll.GUILD, AccessLevel.LEVEL_3), node=unit)
        self.assertEqual(self.company().setup_step, SetupStep.PEOPLE)
        services.update_company(self.company(), legal_name="شرکت ثبت‌شده")
        self.assertEqual(self.company().setup_step, SetupStep.COMPANY)

    def test_going_back_is_allowed_there_is_no_ordering_guard(self):
        domain = tree.create_node(kind="DOMAIN", name="ح", parent=self.root)
        tree.create_node(kind="UNIT", name="و", parent=domain)
        tree.create_node(kind="DOMAIN", name="ح۲", parent=self.root)
        self.assertEqual(self.company().setup_step, SetupStep.DOMAINS)

    def test_a_failed_write_does_not_move_it(self):
        domain = tree.create_node(kind="DOMAIN", name="ح", parent=self.root)
        with self.assertRaises(ConflictError):
            tree.create_node(kind="DOMAIN", name="ح", parent=self.root)  # duplicate name
        self.assertEqual(self.company().setup_step, SetupStep.DOMAINS)
        with self.assertRaises(Exception):
            tree.create_node(kind="SECTION", name="ب", parent=domain)  # wrong parent kind
        self.assertEqual(self.company().setup_step, SetupStep.DOMAINS)

    def test_once_setup_is_complete_writes_no_longer_touch_it(self):
        boss = make_user("4000000002", AccessRoll.EMPLOYER, AccessLevel.LEVEL_1)
        memberships.add_membership(user=boss, node=self.root, is_lead=True, is_primary=True)
        self.client.post(reverse("setup-complete"))
        tree.create_node(kind="DOMAIN", name="ح", parent=self.root)
        services.update_company(self.company(), legal_name="بعداً")
        self.assertEqual(self.company().setup_step, SetupStep.DONE)

    def test_it_is_a_no_op_before_a_company_exists(self):
        from .setup_state import advance_step

        Membership.objects.all().delete()
        Company.objects.all().delete()
        advance_step(SetupStep.UNITS)  # must not raise or create anything
        self.assertFalse(Company.objects.exists())


@skipUnlessDBFeature("has_select_for_update")
@override_settings(CACHES=LOCMEM_CACHE, RATELIMIT_ENABLE=False)
class SetupConcurrencyTests(Threaded, TransactionTestCase):
    """Real threads: the property the two singleton guards (`uniq_developer_account`,
    `Company(pk=1)`) exist for."""

    def dev(self, i, code=None):
        return {"full_name": f"توسعه‌دهنده {i}", "national_code": code or f"960000{i:04d}", "mobile_phone": "", "password": STRONG}

    def assert_exactly_one_ok(self, results, losers, codes):
        ok = [r for r in results if r[0] == "ok"]
        errors = [r[1] for r in results if r[0] == "err"]
        self.assertEqual(len(ok), 1, results)
        self.assertEqual(len(errors), losers, results)
        self.assertTrue(all(isinstance(e, ConflictError) and e.payload["code"] in codes for e in errors), errors)
        return ok[0][1]

    def test_concurrent_developer_bootstraps_create_exactly_one_developer(self):
        results = self.run_concurrently(lambda i: bootstrap.bootstrap_developer(**self.dev(i)), 5)
        self.assert_exactly_one_ok(results, losers=4, codes=("developer_exists",))
        self.assertEqual(User.objects.count(), 1)
        self.assertTrue(User.objects.get().is_developer)

    def test_concurrent_developer_bootstraps_of_the_same_national_code_still_leave_one(self):
        results = self.run_concurrently(
            lambda i: bootstrap.bootstrap_developer(**self.dev(0, code="9600000099")), 5
        )
        self.assert_exactly_one_ok(results, losers=4, codes=("developer_exists", "national_code_exists"))
        self.assertEqual(User.objects.count(), 1)

    def test_concurrent_company_starts_create_exactly_one_company(self):
        bootstrap.bootstrap_developer(**self.dev(0))
        results = self.run_concurrently(lambda i: bootstrap.start_company(company_name=f"شرکت {i}"), 5)
        self.assert_exactly_one_ok(results, losers=4, codes=("already_bootstrapped",))
        self.assertEqual((Company.objects.count(), OrgNode.objects.count(), Membership.objects.count()), (1, 1, 0))

    def test_concurrent_completions_change_exactly_one_row(self):
        bootstrap.bootstrap_developer(**self.dev(0))
        company = bootstrap.start_company(company_name="شرکت")
        boss = make_user("9700000001", AccessRoll.EMPLOYER, AccessLevel.LEVEL_1)
        memberships.add_membership(user=boss, node=company.root, is_lead=True, is_primary=True)
        results = self.run_concurrently(lambda i: bootstrap.complete_setup(), 5)
        self.assertEqual(len([r for r in results if r[0] == "ok"]), 1, results)
        errors = [r[1] for r in results if r[0] == "err"]
        self.assertTrue(all(isinstance(e, ConflictError) and e.payload["code"] == "already_completed" for e in errors), errors)
