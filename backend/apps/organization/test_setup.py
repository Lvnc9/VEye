"""First-run setup — bootstrap (no token since 2026-09-25), start, complete, status, the wizard's bookmark."""
from types import SimpleNamespace
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
from .tests import Threaded

STRONG = "Qz7-vector-maple-93"

MANAGER = {
    "full_name": "  علی   رضايي ",
    "national_code": "۱۲۳۴۵۶۷۸۹۰",
    "mobile_phone": "۰۹۱۲ ۱۱۱ ۲۲۳۳",
    "password": STRONG,
}


def payload(**overrides):
    body = {"company_name": "  وپورویر ", "manager": dict(MANAGER)}
    body.update(overrides)
    return body


@override_settings(CACHES=LOCMEM_CACHE, RATELIMIT_ENABLE=False)
class SetupCase(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=False)
        self.url = reverse("setup-bootstrap")

    def post(self, body=None, client=None, **headers):
        return (client or self.client).post(self.url, payload() if body is None else body, format="json", **headers)

    def nothing_was_created(self):
        self.assertFalse(Company.objects.exists())
        self.assertFalse(OrgNode.objects.exists())
        self.assertFalse(Membership.objects.exists())


class SetupStatusTests(SetupCase):
    def status(self):
        return self.client.get(reverse("setup-status"))

    def test_a_fresh_database_says_setup_is_needed(self):
        response = self.status()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"needed": True, "has_users": False, "step": None})

    def test_it_is_public_and_ignores_a_bad_session_cookie(self):
        self.client.cookies["access_token"] = "garbage.token.value"
        self.assertEqual(self.status().status_code, 200)

    def test_has_users_means_an_active_managing_director_exists(self):
        importer = User.objects.create_user("9100000001", None, full_name="import_user", access_roll="EMPLOYER",
                                            access_level="L1", is_active=False)
        make_user("9100000002", AccessRoll.GUILD, AccessLevel.LEVEL_3)
        make_user("9100000003", AccessRoll.EMPLOYER, AccessLevel.LEVEL_2)
        self.assertFalse(self.status().data["has_users"])  # inactive, صفی and L2 do not count
        make_user("9100000004", AccessRoll.EMPLOYER, AccessLevel.LEVEL_1)
        self.assertTrue(self.status().data["has_users"])
        self.assertFalse(importer.is_active)

    def test_it_answers_only_three_keys_and_no_store(self):
        make_user("9100000005", AccessRoll.EMPLOYER, AccessLevel.LEVEL_1)
        response = self.status()
        self.assertEqual(set(response.data), {"needed", "has_users", "step"})
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_after_bootstrap_it_reports_the_step_and_no_longer_needs_setup(self):
        self.post()
        self.assertEqual(self.status().data, {"needed": False, "has_users": True, "step": SetupStep.DOMAINS})


class NoTokenTests(SetupCase):
    """The setup token is gone (owner, 2026-09-25): a fresh database is set up from the form alone."""

    def test_a_fresh_database_is_bootstrapped_with_no_token_at_all(self):
        self.assertEqual(self.post().status_code, 201)
        self.assertTrue(Company.objects.exists())

    def test_a_leftover_token_header_or_setting_changes_nothing(self):
        with override_settings(SETUP_TOKEN="whatever"):
            response = self.post(HTTP_X_VEYE_SETUP_TOKEN="wrong")
        self.assertEqual(response.status_code, 201)

    @override_settings(RATELIMIT_ENABLE=True, SETUP_RATELIMIT_RATE="3/m")
    def test_every_attempt_counts_against_the_per_ip_limit(self):
        codes = [self.post().status_code for _ in range(5)]
        self.assertEqual(codes, [201, 409, 409, 403, 403])  # the 403s are the limiter


class BootstrapTests(SetupCase):
    def test_it_creates_the_company_the_root_the_manager_and_their_membership(self):
        response = self.post()
        self.assertEqual(response.status_code, 201, response.data)

        company = Company.objects.get()
        self.assertEqual(company.pk, 1)
        self.assertEqual(company.root.name, "وپورویر")  # normalised, trimmed
        self.assertEqual(company.root.kind, OrgNodeKind.COMPANY)
        self.assertEqual(company.setup_step, SetupStep.DOMAINS)
        self.assertIsNone(company.setup_completed_at)

        user = User.objects.get()
        self.assertEqual((user.access_roll, user.access_level), (AccessRoll.EMPLOYER, AccessLevel.LEVEL_1))
        self.assertEqual(user.title, "مدیر عامل")
        self.assertEqual(user.full_name, "علی رضایی")
        self.assertEqual(user.national_code, "1234567890")  # Persian digits -> ASCII
        self.assertEqual(user.mobile_phone, "09121112233")
        self.assertTrue(user.check_password(STRONG))
        self.assertFalse(user.is_superuser or user.is_staff)  # a Django-admin concept, not needed in-app

        membership = Membership.objects.get()
        self.assertEqual((membership.user, membership.node), (user, company.root))
        self.assertTrue(membership.is_lead and membership.is_primary)
        self.assertEqual(company.setup_step, SetupStep.DOMAINS)  # bootstrap's own membership did not move the bookmark

    def test_the_manager_holds_every_capability_including_the_new_ones(self):
        self.post()
        user = User.objects.get()
        self.assertEqual(user.capabilities, frozenset(Capability.values))

    def test_the_new_manager_is_signed_in_and_the_wizard_can_continue_under_that_session(self):
        response = self.post()
        for name in (settings.JWT_ACCESS_COOKIE_NAME, settings.JWT_REFRESH_COOKIE_NAME):
            self.assertTrue(response.cookies[name]["httponly"], name)
        me = self.client.get(reverse("auth-me"))  # the cookie jar carries the session
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data["national_code"], "1234567890")
        # ...and the ordinary org API works with it, no other setup endpoint involved.
        root = Company.objects.get().root
        made = self.client.post(reverse("org-node-list"), {"kind": "DOMAIN", "name": "حوزه یک", "parent": root.pk}, format="json")
        self.assertEqual(made.status_code, 201, made.data)

    def test_the_response_never_contains_the_password_or_its_hash(self):
        response = self.post()
        text = response.content.decode()
        self.assertNotIn(STRONG, text)
        self.assertNotIn(User.objects.get().password, text)
        self.assertNotIn("password", response.data["user"])
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_the_company_payload_is_the_ordinary_one(self):
        company = self.post().data["company"]
        self.assertEqual((company["name"], company["setup_step"]), ("وپورویر", SetupStep.DOMAINS))

    def test_a_second_bootstrap_is_a_409_and_changes_nothing(self):
        self.post()
        again = self.post(payload(manager={**MANAGER, "national_code": "9999999999"}))
        self.assertEqual((again.status_code, again.data["code"]), (409, "already_bootstrapped"))
        self.assertEqual((User.objects.count(), Company.objects.count(), OrgNode.objects.count()), (1, 1, 1))

    def test_a_duplicate_national_code_is_a_409_with_everything_rolled_back(self):
        make_user("1234567890", AccessRoll.GUILD, AccessLevel.LEVEL_3)
        response = self.post()
        self.assertEqual((response.status_code, response.data["code"]), (409, "national_code_exists"))
        self.nothing_was_created()
        self.assertEqual(User.objects.count(), 1)

    def test_a_national_code_taken_after_the_pre_check_is_still_a_409(self):
        """The window between "nobody has this code" and the insert: someone else (personnel
        registration, another request) takes it. The unique constraint must give the same 409 and
        roll the root node and Company back — simulated deterministically."""
        real_create_root = tree.create_root

        def take_the_code_first(**kwargs):
            make_user("1234567890", AccessRoll.GUILD, AccessLevel.LEVEL_3)
            return real_create_root(**kwargs)

        with mock.patch.object(tree, "create_root", side_effect=take_the_code_first):
            response = self.post()
        self.assertEqual((response.status_code, response.data["code"]), (409, "national_code_exists"))
        self.nothing_was_created()

    def test_a_failure_after_the_first_write_leaves_no_half_bootstrapped_state(self):
        """The root node and Company are written before the user. If anything later fails they must
        vanish with it — the property the single transaction exists for."""
        with mock.patch.object(memberships, "add_membership", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                bootstrap.bootstrap(company_name="شرکت", manager=dict(MANAGER) | {"national_code": "1234567890"})
        self.nothing_was_created()
        self.assertFalse(User.objects.exists())

    def test_bad_payloads_are_400s_and_create_nothing(self):
        cases = {
            "no company name": {"manager": MANAGER},
            "blank company name": payload(company_name="   "),
            "no manager": {"company_name": "شرکت"},
            "manager missing password": payload(manager={k: v for k, v in MANAGER.items() if k != "password"}),
            "manager missing name": payload(manager={k: v for k, v in MANAGER.items() if k != "full_name"}),
            "blank national code": payload(manager={**MANAGER, "national_code": "  "}),
        }
        for label, body in cases.items():
            with self.subTest(label):
                self.assertEqual(self.post(body).status_code, 400)
        self.nothing_was_created()

    def test_the_password_must_pass_djangos_validators_in_persian(self):
        for label, password in {"short": "Ab1-x", "all digits": "839201746512", "common": "password123",
                                "like the name": "1234567890"}.items():
            with self.subTest(label):
                response = self.post(payload(manager={**MANAGER, "password": password}))
                self.assertEqual(response.status_code, 400)
                self.assertIn("password", response.data["manager"] if "manager" in response.data else response.data)
        self.nothing_was_created()

    def test_a_password_with_leading_or_trailing_spaces_is_kept_exactly(self):
        self.post(payload(manager={**MANAGER, "password": "  " + STRONG + "  "}))
        self.assertTrue(User.objects.get().check_password("  " + STRONG + "  "))


class ManagerExistsTests(SetupCase):
    """Once an active مدیر عامل exists, the anonymous form is closed: they sign in and press start."""

    def setUp(self):
        super().setUp()
        self.boss = make_user("2000000001", AccessRoll.EMPLOYER, AccessLevel.LEVEL_1, password="their-own-pass-1")

    def test_the_anonymous_form_is_a_persian_409_and_creates_nothing(self):
        response = self.post()
        self.assertEqual((response.status_code, response.data["code"]), (409, "manager_exists"))
        self.assertIn("وارد شوید", str(response.data["detail"]))
        self.nothing_was_created()
        self.assertEqual(User.objects.count(), 1)
        self.assertNotIn(settings.JWT_ACCESS_COOKIE_NAME, response.cookies)

    def test_naming_the_existing_manager_anonymously_is_not_a_way_in(self):
        response = self.post({"company_name": "شرکت", "existing_manager_national_code": "2000000001"})
        self.assertEqual(response.status_code, 400)  # the promotion field is gone; `manager` is required
        self.nothing_was_created()

    def test_an_inactive_or_lower_account_does_not_close_the_form(self):
        self.boss.is_active = False
        self.boss.save(update_fields=["is_active"])
        make_user("2000000002", AccessRoll.EMPLOYER, AccessLevel.LEVEL_2)
        make_user("2000000003", AccessRoll.HEADQUARTERS, AccessLevel.LEVEL_1)
        self.assertEqual(self.post().status_code, 201)


class PromoteExistingManagerServiceTests(SetupCase):
    """The promotion path `setup/start/` uses, at the service level."""

    def setUp(self):
        super().setUp()
        self.boss = make_user("2000000001", AccessRoll.EMPLOYER, AccessLevel.LEVEL_1, password="their-own-pass-1")

    def promote(self, code="2000000001"):
        return bootstrap.bootstrap(company_name="شرکت", existing_manager_national_code=code)

    def test_an_existing_managing_director_is_given_the_root_membership_and_keeps_their_password(self):
        before = self.boss.password
        result = self.promote()
        self.assertFalse(result.created_user)
        membership = Membership.objects.get()
        self.assertEqual((membership.user, membership.is_lead, membership.is_primary), (self.boss, True, True))
        self.boss.refresh_from_db()
        self.assertEqual(self.boss.password, before)

    def test_only_an_active_managing_director_is_eligible_and_the_answer_is_the_same_for_all(self):
        make_user("2000000002", AccessRoll.EMPLOYER, AccessLevel.LEVEL_2)
        make_user("2000000003", AccessRoll.GUILD, AccessLevel.LEVEL_3)
        make_user("2000000004", AccessRoll.HEADQUARTERS, AccessLevel.LEVEL_1)
        User.objects.create_user("2000000005", None, full_name="import_user", access_roll="EMPLOYER",
                                 access_level="L1", is_active=False)
        for code in ("2000000002", "2000000003", "2000000004", "2000000005", "2999999999"):
            with self.subTest(code=code):
                with self.assertRaises(ConflictError) as caught:
                    self.promote(code)
                self.assertEqual(caught.exception.payload["code"], "manager_not_eligible")
        self.nothing_was_created()


class SetupStartTests(SetupCase):
    """`POST /setup/start/`: the signed-in مدیر عامل's one button."""

    def setUp(self):
        super().setUp()
        self.start_url = reverse("setup-start")
        self.boss = make_user("2000000001", AccessRoll.EMPLOYER, AccessLevel.LEVEL_1, password="their-own-pass-1")

    def start(self, user=None, body=None):
        self.client.force_authenticate(user or self.boss)
        return self.client.post(self.start_url, body or {}, format="json")

    def test_the_manager_starts_setup_with_one_press(self):
        before = self.boss.password
        response = self.start()
        self.assertEqual(response.status_code, 201, response.data)
        company = Company.objects.get()
        self.assertEqual((company.root.name, company.setup_step), ("شرکت من", SetupStep.DOMAINS))
        membership = Membership.objects.get()
        self.assertEqual((membership.user, membership.node, membership.is_lead, membership.is_primary),
                         (self.boss, company.root, True, True))
        self.assertEqual(User.objects.count(), 1)
        self.boss.refresh_from_db()
        self.assertEqual(self.boss.password, before)
        self.assertEqual(response.data["user"]["id"], self.boss.id)
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_a_company_name_can_be_given(self):
        self.assertEqual(self.start(body={"company_name": "  وپورویر "}).status_code, 201)
        self.assertEqual(Company.objects.get().root.name, "وپورویر")

    def test_it_needs_a_session(self):
        self.assertEqual(self.client.post(self.start_url, {}, format="json").status_code, 401)
        self.nothing_was_created()

    def test_only_an_active_managing_director_may_start_and_it_is_a_persian_403(self):
        for user in (
            make_user("2000000002", AccessRoll.EMPLOYER, AccessLevel.LEVEL_2),
            make_user("2000000003", AccessRoll.GUILD, AccessLevel.LEVEL_3),
            make_user("2000000004", AccessRoll.HEADQUARTERS, AccessLevel.LEVEL_1),
        ):
            with self.subTest(user=user.national_code):
                response = self.start(user)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(str(response.data["detail"]), "راه‌اندازی را فقط مدیر عامل می‌تواند شروع کند.")
        self.nothing_was_created()

    def test_it_cannot_name_somebody_else_as_manager(self):
        other = make_user("2000000009", AccessRoll.EMPLOYER, AccessLevel.LEVEL_1)
        body = {"existing_manager_national_code": other.national_code, "manager": dict(MANAGER)}
        self.assertEqual(self.start(body=body).status_code, 201)
        self.assertEqual(Membership.objects.get().user, self.boss)
        self.assertFalse(User.objects.filter(national_code="1234567890").exists())

    def test_a_second_start_is_a_409_and_the_anonymous_form_stays_shut_too(self):
        self.assertEqual(self.start().status_code, 201)
        again = self.start()
        self.assertEqual((again.status_code, again.data["code"]), (409, "already_bootstrapped"))
        self.client.force_authenticate(None)
        self.assertEqual(self.post().status_code, 409)
        self.assertEqual(Company.objects.count(), 1)


class CompleteTests(SetupCase):
    def setUp(self):
        super().setUp()
        self.post()
        self.url_complete = reverse("setup-complete")

    def test_it_needs_a_session(self):
        self.client.cookies.clear()
        self.assertEqual(self.client.post(self.url_complete).status_code, 401)

    def test_it_needs_manage_organization(self):
        guild = make_user("3000000001", AccessRoll.GUILD, AccessLevel.LEVEL_3)
        self.client.cookies.clear()
        self.client.force_authenticate(guild)
        self.assertEqual(self.client.post(self.url_complete).status_code, 403)
        self.assertIsNone(Company.objects.get().setup_completed_at)

    def test_the_manager_completes_setup_once(self):
        response = self.client.post(self.url_complete)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data, {"needed": False, "has_users": True, "step": SetupStep.DONE})
        company = Company.objects.get()
        self.assertEqual(company.setup_step, SetupStep.DONE)
        self.assertIsNotNone(company.setup_completed_at)

        again = self.client.post(self.url_complete)
        self.assertEqual((again.status_code, again.data["code"]), (409, "already_completed"))
        self.assertEqual(Company.objects.get().setup_completed_at, company.setup_completed_at)  # untouched

    def test_it_needs_no_structure(self):
        self.assertEqual(OrgNode.objects.count(), 1)  # just the company root
        self.assertEqual(self.client.post(self.url_complete).status_code, 200)

    def test_without_a_company_it_is_a_404(self):
        Conversation.objects.all().delete()  # every node's channel PROTECTs it
        Membership.objects.all().delete()
        Company.objects.all().delete()
        OrgNode.objects.all().delete()
        self.client.force_authenticate(User.objects.get())
        self.assertEqual(self.client.post(self.url_complete).status_code, 404)

    def test_bootstrap_stays_dead_after_completion(self):
        self.client.post(self.url_complete)
        self.assertEqual(self.post(payload(manager={**MANAGER, "national_code": "5555555555"})).status_code, 409)


class BookmarkTests(SetupCase):
    """`Company.setup_step` follows the last thing written, in the same transaction."""

    def setUp(self):
        super().setUp()
        self.post()
        self.company = lambda: Company.objects.get()
        self.root = Company.objects.get().root
        self.manager = User.objects.get()

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
    """Real threads: the property the Company(pk=1) guard exists for."""

    def manager(self, i, code=None):
        return {"full_name": f"مدیر {i}", "national_code": code or f"96000000{i:02d}", "mobile_phone": "", "password": STRONG}

    def assert_exactly_one_bootstrap(self, results, losers, codes=("already_bootstrapped",)):
        ok = [r for r in results if r[0] == "ok"]
        errors = [r[1] for r in results if r[0] == "err"]
        self.assertEqual(len(ok), 1, results)
        self.assertEqual(len(errors), losers, results)
        self.assertTrue(all(isinstance(e, ConflictError) and e.payload["code"] in codes for e in errors), errors)
        self.assertEqual(
            (Company.objects.count(), OrgNode.objects.count(), Membership.objects.count(), User.objects.count()),
            (1, 1, 1, 1),  # the losers' roots and users rolled back with them
        )

    def test_concurrent_bootstraps_create_exactly_one_company(self):
        results = self.run_concurrently(
            lambda i: bootstrap.bootstrap(company_name=f"شرکت {i}", manager=self.manager(i)), 5
        )
        self.assert_exactly_one_bootstrap(results, losers=4)
        self.assertEqual(Company.objects.get().root.name, User.objects.get().full_name.replace("مدیر", "شرکت"))

    def test_concurrent_bootstraps_of_the_same_national_code_still_leave_one(self):
        results = self.run_concurrently(
            lambda i: bootstrap.bootstrap(company_name="شرکت", manager=self.manager(0, "9600000099")), 5
        )
        self.assert_exactly_one_bootstrap(results, losers=4, codes=("already_bootstrapped", "national_code_exists"))

    def test_concurrent_promotions_promote_exactly_once(self):
        make_user("9700000001", AccessRoll.EMPLOYER, AccessLevel.LEVEL_1)
        results = self.run_concurrently(
            lambda i: bootstrap.bootstrap(company_name="شرکت", existing_manager_national_code="9700000001"), 4
        )
        self.assertEqual(len([r for r in results if r[0] == "ok"]), 1, results)
        self.assertEqual((Company.objects.count(), Membership.objects.count()), (1, 1))

    def test_concurrent_completions_change_exactly_one_row(self):
        bootstrap.bootstrap(company_name="شرکت", manager=self.manager(1))
        results = self.run_concurrently(lambda i: bootstrap.complete_setup(), 5)
        self.assertEqual(len([r for r in results if r[0] == "ok"]), 1, results)
        errors = [r[1] for r in results if r[0] == "err"]
        self.assertTrue(all(isinstance(e, ConflictError) and e.payload["code"] == "already_completed" for e in errors), errors)
