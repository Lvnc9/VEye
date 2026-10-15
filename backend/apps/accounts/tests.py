from unittest import mock

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from .models import AccessLevel, AccessRoll, Capability, User

# Tests run against an in-memory cache so they don't need a live Redis for
# the JWT blacklist / login rate limiter.
LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "veye-tests",
    }
}


def make_user(national_code, roll, level, password="test-pass-123", **extra):
    return User.objects.create_user(
        national_code=national_code,
        password=password,
        full_name=extra.pop("full_name", f"کاربر {national_code}"),
        access_roll=roll,
        access_level=level,
        **extra,
    )


class TitleMatrixTests(TestCase):
    """The 3x3 roll x level -> سمت matrix, ported from V_1.0 register.py:739-769."""

    def test_every_combination_resolves_to_a_persian_title(self):
        expected = {
            (AccessRoll.EMPLOYER, AccessLevel.LEVEL_1): "مدیر عامل",
            (AccessRoll.EMPLOYER, AccessLevel.LEVEL_2): "رئیس هیئت مدیره",
            (AccessRoll.EMPLOYER, AccessLevel.LEVEL_3): "عضو هیئت مدیره",
            (AccessRoll.HEADQUARTERS, AccessLevel.LEVEL_1): "نماینده مدیریت",
            (AccessRoll.HEADQUARTERS, AccessLevel.LEVEL_2): "معاون/مشاور",
            (AccessRoll.HEADQUARTERS, AccessLevel.LEVEL_3): "مدیر/رئیس",
            (AccessRoll.GUILD, AccessLevel.LEVEL_1): "سرپرست",
            (AccessRoll.GUILD, AccessLevel.LEVEL_2): "کارشناس",
            (AccessRoll.GUILD, AccessLevel.LEVEL_3): "کارمند/اپراتور",
        }
        self.assertEqual(len(expected), 9)
        for (roll, level), title in expected.items():
            user = User(access_roll=roll, access_level=level)
            self.assertEqual(user.title, title, f"{roll}/{level}")


class CapabilityTests(TestCase):
    """What roll × level grants (Phase 14, owner's decision 2026-09-30): **not** تدوین / تایید / تصویب — those
    follow the org chart (documents/authority.py). The roll keeps printing, personnel, the organisation and
    projects; only the مدیر عامل (and a superuser) holds every capability.
    """

    def test_guild_only_prints(self):
        user = User(access_roll=AccessRoll.GUILD, access_level=AccessLevel.LEVEL_2)
        self.assertEqual(user.capabilities, frozenset({Capability.PRINT_DOCUMENT}))

    def test_headquarters_prints_and_creates_projects(self):
        user = User(access_roll=AccessRoll.HEADQUARTERS, access_level=AccessLevel.LEVEL_2)
        self.assertEqual(
            user.capabilities,
            frozenset(
                {Capability.PRINT_DOCUMENT, Capability.CREATE_PROJECT, Capability.VIEW_REPORTS, Capability.MANAGE_QUALITY}
            ),
        )

    def test_no_roll_below_the_managing_director_grants_a_document_step(self):
        steps = {Capability.CREATE_DOCUMENT, Capability.CONFIRM_DOCUMENT, Capability.APPROVE_DOCUMENT}
        for roll in AccessRoll.values:
            for level in AccessLevel.values:
                if (roll, level) == (AccessRoll.EMPLOYER, AccessLevel.LEVEL_1):
                    continue
                held = User(access_roll=roll, access_level=level).capabilities
                self.assertFalse(steps & held, (roll, level))

    def test_the_board_manages_personnel_and_the_organisation_but_no_longer_approves(self):
        # کارفرمایی below the مدیر عامل: رئیس و عضو هیئت مدیره.
        for level in (AccessLevel.LEVEL_2, AccessLevel.LEVEL_3):
            user = User(access_roll=AccessRoll.EMPLOYER, access_level=level)
            self.assertEqual(
                user.capabilities,
                frozenset(
                    {
                        Capability.MANAGE_PERSONNEL,
                        Capability.PRINT_DOCUMENT,
                        Capability.MANAGE_ORGANIZATION,
                        Capability.MANAGE_MEMBERSHIP,
                        Capability.CREATE_PROJECT,
                        Capability.VIEW_REPORTS,
                        Capability.MANAGE_QUALITY,
                    }
                ),
            )
            self.assertFalse(user.has_capability(Capability.APPROVE_DOCUMENT))

    def test_the_managing_director_holds_every_capability(self):
        # Requested by the product owner: مدیر عامل = کارفرمایی لول ۱ can do everything in the app.
        ceo = User(access_roll=AccessRoll.EMPLOYER, access_level=AccessLevel.LEVEL_1)
        self.assertEqual(ceo.title, "مدیر عامل")
        self.assertEqual(ceo.capabilities, frozenset(Capability.values))
        for capability in Capability.values:
            self.assertTrue(ceo.has_capability(capability), capability)

    def test_only_the_managing_director_gains_anything(self):
        # The exception is one position, not the whole roll or the whole level.
        for roll in AccessRoll.values:
            for level in AccessLevel.values:
                user = User(access_roll=roll, access_level=level)
                is_ceo = (roll, level) == (AccessRoll.EMPLOYER, AccessLevel.LEVEL_1)
                self.assertEqual(user.capabilities == frozenset(Capability.values), is_ceo, (roll, level))

    def test_the_organisation_capabilities_by_roll(self):
        # docs/11-phase-7-9-plan.md §5.1. صفی gains nothing: if everyone could create projects the
        # capability would be decorative, and it keeps the document axis untouched.
        org_axis = {Capability.MANAGE_ORGANIZATION, Capability.MANAGE_MEMBERSHIP, Capability.CREATE_PROJECT}
        expected = {
            AccessRoll.GUILD: set(),
            AccessRoll.HEADQUARTERS: {Capability.CREATE_PROJECT},
            AccessRoll.EMPLOYER: org_axis,
        }
        for roll, granted in expected.items():
            for level in (AccessLevel.LEVEL_2, AccessLevel.LEVEL_3):  # L1 employer is the مدیر عامل, below
                held = User(access_roll=roll, access_level=level).capabilities
                self.assertEqual(set(held) & org_axis, granted, (roll, level))

    def test_no_capability_reads_other_peoples_conversations(self):
        """The مدیر عامل is built from `Capability.values`, so any such capability would silently
        hand him everyone's private messages. Chat access is membership-based only — do not add one."""
        for value in Capability.values:
            for word in ("conversation", "chat", "message", "inbox"):
                self.assertNotIn(word, value)

    def test_superuser_has_everything(self):
        user = User(access_roll=AccessRoll.GUILD, access_level=AccessLevel.LEVEL_3, is_superuser=True)
        self.assertEqual(set(user.capabilities), set(Capability.values))


@override_settings(CACHES=LOCMEM_CACHE, RATELIMIT_ENABLE=False)
class AuthFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=False)
        self.password = "correct-horse-battery"
        self.user = make_user("1111111111", AccessRoll.GUILD, AccessLevel.LEVEL_2, password=self.password)

    def test_login_sets_httponly_jwt_cookies(self):
        response = self.client.post(
            reverse("auth-login"),
            {"national_code": self.user.national_code, "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        access = response.cookies.get(settings.JWT_ACCESS_COOKIE_NAME)
        refresh = response.cookies.get(settings.JWT_REFRESH_COOKIE_NAME)
        self.assertIsNotNone(access)
        self.assertIsNotNone(refresh)
        self.assertTrue(access["httponly"])
        self.assertTrue(refresh["httponly"])

    def test_login_rejects_wrong_password(self):
        response = self.client.post(
            reverse("auth-login"),
            {"national_code": self.user.national_code, "password": "wrong"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_credentials_are_checked_as_a_pair(self):
        """V_1.0 checked the national code against the key set and the password
        against the value set independently (main.py:74-79), so any valid user
        plus any other user's password authenticated. Guard against that.
        """
        other = make_user("2222222222", AccessRoll.EMPLOYER, AccessLevel.LEVEL_1, password="other-password")
        response = self.client.post(
            reverse("auth-login"),
            {"national_code": self.user.national_code, "password": "other-password"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertTrue(User.objects.filter(pk=other.pk).exists())

    def test_me_returns_title_and_capabilities(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("auth-me"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["title"], "کارشناس")
        # A صفی who leads nothing: the roll gives printing only; /auth/me/ adds what the chart grants (nothing here).
        self.assertEqual(response.data["capabilities"], [Capability.PRINT_DOCUMENT])

    def test_me_requires_authentication(self):
        self.assertEqual(self.client.get(reverse("auth-me")).status_code, 401)


@override_settings(CACHES=LOCMEM_CACHE, RATELIMIT_ENABLE=False)
class PersonnelPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=False)
        self.employer = make_user("3333333333", AccessRoll.EMPLOYER, AccessLevel.LEVEL_1)
        self.guild = make_user("4444444444", AccessRoll.GUILD, AccessLevel.LEVEL_3)
        self.payload = {
            "national_code": "5555555555",
            "full_name": "پرسنل جدید",
            "mobile_phone": "09120000000",
            "access_roll": AccessRoll.GUILD,
            "access_level": AccessLevel.LEVEL_2,
            "password": "a-new-password-1",
        }

    def test_employer_can_create_personnel(self):
        self.client.force_authenticate(user=self.employer)
        response = self.client.post(reverse("personnel-list"), self.payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(User.objects.filter(national_code="5555555555").exists())

    def test_created_personnel_actually_persists(self):
        """V_1.0's register screen wrote nothing anywhere — successful() just
        set a label (register.py:770-774). This is the regression guard.
        """
        self.client.force_authenticate(user=self.employer)
        self.client.post(reverse("personnel-list"), self.payload, format="json")
        created = User.objects.get(national_code="5555555555")
        self.assertEqual(created.full_name, "پرسنل جدید")
        self.assertEqual(created.title, "کارشناس")
        self.assertTrue(created.check_password("a-new-password-1"))

    def test_guild_cannot_create_personnel(self):
        self.client.force_authenticate(user=self.guild)
        response = self.client.post(reverse("personnel-list"), self.payload, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(national_code="5555555555").exists())

    def test_any_authenticated_user_can_read_the_directory(self):
        self.client.force_authenticate(user=self.guild)
        self.assertEqual(self.client.get(reverse("personnel-list")).status_code, 200)

    def test_anonymous_cannot_read_the_directory(self):
        self.assertEqual(self.client.get(reverse("personnel-list")).status_code, 401)

    def test_is_staff_cannot_be_escalated_through_the_api(self):
        self.client.force_authenticate(user=self.employer)
        response = self.client.post(
            reverse("personnel-list"), {**self.payload, "is_staff": True}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertFalse(User.objects.get(national_code="5555555555").is_staff)

    def test_title_endpoint_resolves_the_matrix(self):
        self.client.force_authenticate(user=self.guild)
        response = self.client.get(reverse("personnel-title", args=[self.employer.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["title"], "مدیر عامل")


@override_settings(CACHES=LOCMEM_CACHE, RATELIMIT_ENABLE=False)
class PersonnelDeletionTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=False)
        self.employer = make_user("8000000001", AccessRoll.EMPLOYER, AccessLevel.LEVEL_1)
        self.client.force_authenticate(self.employer)

    def test_someone_with_no_documents_can_be_deleted(self):
        person = make_user("8000000002", AccessRoll.GUILD, AccessLevel.LEVEL_3)
        response = self.client.delete(reverse("personnel-detail", args=[person.pk]))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(User.objects.filter(pk=person.pk).exists())

    def test_an_author_cannot_be_deleted_and_the_answer_says_why(self):
        """Documents reference their author with PROTECT; this used to be a 500."""
        from apps.documents import services

        author = make_user("8000000003", AccessRoll.GUILD, AccessLevel.LEVEL_3)
        services.create_document(user=author, category="INSIDE", title="سند نویسنده", group="FORM")

        response = self.client.delete(reverse("personnel-detail", args=[author.pk]))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "user_has_documents")
        self.assertIn("غیرفعال", response.data["detail"])
        self.assertTrue(User.objects.filter(pk=author.pk).exists())

    def test_deactivating_is_the_supported_way_to_retire_an_author(self):
        from apps.documents import services

        author = make_user("8000000004", AccessRoll.GUILD, AccessLevel.LEVEL_3)
        services.create_document(user=author, category="INSIDE", title="سند دیگر", group="FORM")
        response = self.client.patch(reverse("personnel-detail", args=[author.pk]), {"is_active": False}, format="json")
        self.assertEqual(response.status_code, 200)
        author.refresh_from_db()
        self.assertFalse(author.is_active)


@override_settings(CACHES=LOCMEM_CACHE, RATELIMIT_ENABLE=False)
class PersonnelPlacementTests(TestCase):
    """POST /personnel/ with `placement`: one request registers a person and puts them in the org
    chart (ADR-010 §B). Either both happen or neither does — no more half-placed accounts."""

    def setUp(self):
        from apps.organization import tree
        from apps.organization.models import Company, OrgNodeKind, SetupStep

        self.client = APIClient(enforce_csrf_checks=False)
        self.employer = make_user("6000000001", AccessRoll.EMPLOYER, AccessLevel.LEVEL_1)
        self.root = tree.create_root(name="شرکت نمونه")
        Company.objects.create(pk=1, root=self.root, setup_step=SetupStep.DOMAINS)
        self.unit = tree.create_node(kind=OrgNodeKind.UNIT, name="واحد فروش", parent=self.root)
        self.payload = {
            "national_code": "6100000001",
            "full_name": "پرسنل جدید",
            "mobile_phone": "09120000001",
            "access_roll": AccessRoll.GUILD,
            "access_level": AccessLevel.LEVEL_2,
            "password": "a-new-password-1",
        }

    def test_registers_and_places_in_one_request(self):
        from apps.organization.models import Membership

        self.client.force_authenticate(user=self.employer)
        response = self.client.post(
            reverse("personnel-list"),
            {**self.payload, "placement": {"node": self.unit.pk, "is_lead": True, "position_label": "رئیس فروش"}},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        person = User.objects.get(national_code="6100000001")
        membership = Membership.objects.get(user=person, node=self.unit)
        self.assertTrue(membership.is_lead)
        self.assertTrue(membership.is_primary)
        self.assertEqual(membership.position_label, "رئیس فروش")
        # The response carries the membership too, so the caller never has to ask again.
        self.assertEqual(response.data["membership"]["id"], membership.pk)
        self.assertEqual(response.data["membership"]["node"], self.unit.pk)

    def test_without_placement_nothing_but_the_person_is_created(self):
        from apps.organization.models import Membership

        self.client.force_authenticate(user=self.employer)
        response = self.client.post(reverse("personnel-list"), self.payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertNotIn("membership", response.data)
        self.assertFalse(Membership.objects.filter(user__national_code="6100000001").exists())

    def test_no_permission_to_place_creates_nobody(self):
        """A caller without manage_personnel cannot use a `placement` payload as a side door: the
        outer capability gate still applies first, and a refusal leaves nothing behind."""
        guild = make_user("6000000002", AccessRoll.GUILD, AccessLevel.LEVEL_3)
        self.client.force_authenticate(user=guild)
        response = self.client.post(
            reverse("personnel-list"),
            {**self.payload, "placement": {"node": self.unit.pk}},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(national_code="6100000001").exists())
        from apps.organization.models import Membership

        self.assertFalse(Membership.objects.filter(node=self.unit).exists())

    def test_archived_node_is_409_and_creates_nobody(self):
        from apps.organization import tree

        tree.archive_node(self.unit)
        self.client.force_authenticate(user=self.employer)
        response = self.client.post(
            reverse("personnel-list"),
            {**self.payload, "placement": {"node": self.unit.pk}},
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "node_archived")
        self.assertFalse(User.objects.filter(national_code="6100000001").exists())

    def test_missing_node_is_404_and_creates_nobody(self):
        self.client.force_authenticate(user=self.employer)
        response = self.client.post(
            reverse("personnel-list"),
            {**self.payload, "placement": {"node": 999999}},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(User.objects.filter(national_code="6100000001").exists())

    def test_rollback_on_a_membership_conflict_leaves_no_user(self):
        """Whatever the reason `memberships.add_membership` refuses, the user it was about to
        belong to must not survive either — same transaction, same fate."""
        from apps.core.exceptions import ConflictError

        self.client.force_authenticate(user=self.employer)
        with mock.patch(
            "apps.organization.memberships.add_membership",
            side_effect=ConflictError("تعارض آزمایشی.", code="already_member"),
        ):
            response = self.client.post(
                reverse("personnel-list"),
                {**self.payload, "placement": {"node": self.unit.pk}},
                format="json",
            )
        self.assertEqual(response.status_code, 409)
        self.assertFalse(User.objects.filter(national_code="6100000001").exists())


def make_developer(national_code="7000000001", **extra):
    """The Phase 10 developer account: stored as صفی/لول ۳, which `is_developer` overrides."""
    return make_user(national_code, AccessRoll.GUILD, AccessLevel.LEVEL_3, is_developer=True, **extra)


class DeveloperAccountTests(TestCase):
    """ADR-010: the developer runs setup and registers personnel, and can never sign a document."""

    def test_developer_holds_only_the_setup_capabilities(self):
        developer = make_developer()
        self.assertEqual(
            developer.capabilities,
            frozenset({Capability.MANAGE_ORGANIZATION, Capability.MANAGE_MEMBERSHIP, Capability.MANAGE_PERSONNEL}),
        )
        for document_capability in (
            Capability.CREATE_DOCUMENT,
            Capability.CONFIRM_DOCUMENT,
            Capability.APPROVE_DOCUMENT,
            Capability.PRINT_DOCUMENT,
            Capability.CREATE_PROJECT,
            Capability.VIEW_REPORTS,
            Capability.MANAGE_QUALITY,
        ):
            self.assertFalse(developer.has_capability(document_capability))

    def test_the_flag_wins_over_a_full_access_position(self):
        # Even stored as کارفرمایی/لول ۱ (the مدیر عامل position), a developer gets no document capability.
        developer = User(access_roll=AccessRoll.EMPLOYER, access_level=AccessLevel.LEVEL_1, is_developer=True)
        self.assertFalse(developer.has_capability(Capability.APPROVE_DOCUMENT))

    def test_title_never_reads_as_a_company_position(self):
        self.assertEqual(make_developer().title, "توسعه‌دهنده")

    def test_there_is_at_most_one_developer(self):
        from django.db import IntegrityError, transaction

        make_developer()
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_developer("7000000002")
        # Ordinary accounts are unaffected by the constraint.
        make_user("7000000003", AccessRoll.GUILD, AccessLevel.LEVEL_2)
        make_user("7000000004", AccessRoll.GUILD, AccessLevel.LEVEL_2)


@override_settings(CACHES=LOCMEM_CACHE, RATELIMIT_ENABLE=False)
class DeveloperProtectionApiTests(TestCase):
    """Only the developer may change or delete the developer account (ADR-010)."""

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=False)
        self.developer = make_developer()
        self.ceo = make_user("7100000001", AccessRoll.EMPLOYER, AccessLevel.LEVEL_1)

    def detail(self, user):
        return reverse("personnel-detail", args=[user.pk])

    def test_me_exposes_the_flag(self):
        self.client.force_authenticate(user=self.developer)
        body = self.client.get(reverse("auth-me")).json()
        self.assertTrue(body["is_developer"])
        self.assertEqual(body["title"], "توسعه‌دهنده")

    def test_the_flag_cannot_be_set_through_the_personnel_api(self):
        self.client.force_authenticate(user=self.ceo)
        response = self.client.post(
            reverse("personnel-list"),
            {
                "national_code": "7100000002",
                "full_name": "کسی",
                "access_roll": AccessRoll.GUILD,
                "access_level": AccessLevel.LEVEL_2,
                "password": "a-new-password-1",
                "is_developer": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(User.objects.get(national_code="7100000002").is_developer)

    def test_a_manager_cannot_reset_the_developers_password_or_deactivate_it(self):
        self.client.force_authenticate(user=self.ceo)
        for body in ({"password": "taken-over-123"}, {"is_active": False}):
            response = self.client.patch(self.detail(self.developer), body, format="json")
            self.assertEqual(response.status_code, 403, body)
            self.assertIn("توسعه‌دهنده", response.json()["detail"])
        self.developer.refresh_from_db()
        self.assertTrue(self.developer.is_active)
        self.assertTrue(self.developer.check_password("test-pass-123"))

    def test_a_manager_cannot_delete_the_developer(self):
        self.client.force_authenticate(user=self.ceo)
        self.assertEqual(self.client.delete(self.detail(self.developer)).status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.developer.pk).exists())

    def test_the_developer_may_edit_themselves(self):
        self.client.force_authenticate(user=self.developer)
        response = self.client.patch(self.detail(self.developer), {"mobile_phone": "09121112233"}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_ordinary_personnel_are_unaffected(self):
        person = make_user("7100000003", AccessRoll.GUILD, AccessLevel.LEVEL_2)
        self.client.force_authenticate(user=self.ceo)
        self.assertEqual(self.client.patch(self.detail(person), {"is_active": False}, format="json").status_code, 200)


def _issued_earlier(seconds=5):
    """Tokens minted a few seconds in the past. A revocation in the same second as a login lets that
    login's tokens through (the cutoff is whole seconds, like `iat`); aging them keeps tests exact."""
    from datetime import timedelta

    from rest_framework_simplejwt.utils import aware_utcnow

    return mock.patch(
        "rest_framework_simplejwt.tokens.aware_utcnow", return_value=aware_utcnow() - timedelta(seconds=seconds)
    )


@override_settings(CACHES=LOCMEM_CACHE, RATELIMIT_ENABLE=False)
class PasswordChangeTests(TestCase):
    """Phase 20: choosing your own password; a password someone else chose must be replaced."""

    def setUp(self):
        self.password = "correct-horse-battery"
        self.user = make_user("8100000001", AccessRoll.GUILD, AccessLevel.LEVEL_2, password=self.password)
        self.hr = make_user("8100000002", AccessRoll.EMPLOYER, AccessLevel.LEVEL_1)
        self.client = APIClient(enforce_csrf_checks=False)

    def sign_in(self, client, user, password):
        with _issued_earlier():
            response = client.post(
                reverse("auth-login"), {"national_code": user.national_code, "password": password}, format="json"
            )
        self.assertEqual(response.status_code, 200, response.content)
        return response

    def change(self, client, current, new):
        return client.post(
            reverse("auth-password"), {"current_password": current, "new_password": new}, format="json"
        )

    def test_changing_your_own_password(self):
        self.sign_in(self.client, self.user, self.password)
        response = self.change(self.client, self.password, "a-fresh-secret-42")
        self.assertEqual(response.status_code, 200, response.content)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("a-fresh-secret-42"))
        self.assertFalse(response.json()["must_change_password"])
        # The response re-issued this browser's cookies, so it stays signed in.
        self.assertEqual(self.client.get(reverse("auth-me")).status_code, 200)

    def test_the_current_password_must_be_right(self):
        self.sign_in(self.client, self.user, self.password)
        response = self.change(self.client, "not-my-password", "a-fresh-secret-42")
        self.assertEqual(response.status_code, 400)
        self.assertIn("current_password", response.json())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    def test_the_new_password_must_differ_and_be_strong(self):
        self.sign_in(self.client, self.user, self.password)
        for weak in (self.password, "12345678", "abc"):
            response = self.change(self.client, self.password, weak)
            self.assertEqual(response.status_code, 400, weak)
            self.assertIn("new_password", response.json())

    def test_changing_signs_out_every_other_device(self):
        other = APIClient(enforce_csrf_checks=False)
        self.sign_in(other, self.user, self.password)
        self.sign_in(self.client, self.user, self.password)
        self.assertEqual(self.change(self.client, self.password, "a-fresh-secret-42").status_code, 200)
        self.assertEqual(other.get(reverse("auth-me")).status_code, 401)
        self.assertEqual(other.post(reverse("auth-refresh")).status_code, 401)

    def test_anonymous_cannot_change_a_password(self):
        self.assertEqual(self.change(self.client, self.password, "a-fresh-secret-42").status_code, 401)

    def test_login_records_last_login(self):
        self.assertIsNone(self.user.last_login)
        self.sign_in(self.client, self.user, self.password)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.last_login)

    # --- a password someone else chose ---

    def register(self, password="first-secret-77"):
        hr = APIClient(enforce_csrf_checks=False)
        hr.force_authenticate(user=self.hr)
        response = hr.post(
            reverse("personnel-list"),
            {
                "national_code": "8100000009",
                "full_name": "نیروی تازه",
                "access_roll": AccessRoll.GUILD,
                "access_level": AccessLevel.LEVEL_3,
                "password": password,
            },
            format="json",
        )
        return response

    def test_a_registered_person_must_choose_their_own_password(self):
        response = self.register()
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(response.json()["must_change_password"])
        person = User.objects.get(national_code="8100000009")
        self.assertTrue(person.must_change_password)

        login = self.sign_in(self.client, person, "first-secret-77")
        self.assertTrue(login.json()["must_change_password"])
        self.assertTrue(self.client.get(reverse("auth-me")).json()["must_change_password"])
        blocked = self.client.get(reverse("personnel-list"))
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.json()["code"], "password_change_required")

        self.assertEqual(self.change(self.client, "first-secret-77", "my-own-secret-99").status_code, 200)
        self.assertEqual(self.client.get(reverse("personnel-list")).status_code, 200)
        person.refresh_from_db()
        self.assertFalse(person.must_change_password)

    def test_registration_refuses_a_weak_password(self):
        response = self.register(password="12345678")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json())
        self.assertFalse(User.objects.filter(national_code="8100000009").exists())

    def test_an_hr_reset_forces_a_change_and_signs_the_person_out(self):
        self.sign_in(self.client, self.user, self.password)
        hr = APIClient(enforce_csrf_checks=False)
        hr.force_authenticate(user=self.hr)
        response = hr.patch(
            reverse("personnel-detail", args=[self.user.pk]), {"password": "reset-by-hr-55"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.user.refresh_from_db()
        self.assertTrue(self.user.must_change_password)
        self.assertTrue(self.user.check_password("reset-by-hr-55"))
        self.assertEqual(self.client.get(reverse("auth-me")).status_code, 401)
        self.assertEqual(self.client.post(reverse("auth-refresh")).status_code, 401)

    def test_an_hr_reset_refuses_a_weak_password(self):
        hr = APIClient(enforce_csrf_checks=False)
        hr.force_authenticate(user=self.hr)
        response = hr.patch(reverse("personnel-detail", args=[self.user.pk]), {"password": "8100000001"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    def test_editing_your_own_password_through_the_directory_is_not_a_reset(self):
        developer = make_developer()
        client = APIClient(enforce_csrf_checks=False)
        client.force_authenticate(user=developer)
        response = client.patch(
            reverse("personnel-detail", args=[developer.pk]), {"password": "developer-own-77"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        developer.refresh_from_db()
        self.assertFalse(developer.must_change_password)
        self.assertIsNone(developer.sessions_valid_after)

    def test_editing_other_fields_does_not_force_a_change(self):
        hr = APIClient(enforce_csrf_checks=False)
        hr.force_authenticate(user=self.hr)
        hr.patch(reverse("personnel-detail", args=[self.user.pk]), {"mobile_phone": "09120000001"}, format="json")
        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)
        self.assertIsNone(self.user.sessions_valid_after)
