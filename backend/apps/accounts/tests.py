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
    """The access policy confirmed with the product owner:
    create -> صفی/ستادی, confirm -> ستادی, approve -> کارفرمایی.
    """

    def test_guild_can_only_create(self):
        user = User(access_roll=AccessRoll.GUILD, access_level=AccessLevel.LEVEL_2)
        self.assertEqual(
            user.capabilities, frozenset({Capability.CREATE_DOCUMENT, Capability.PRINT_DOCUMENT})
        )

    def test_headquarters_can_create_and_confirm(self):
        user = User(access_roll=AccessRoll.HEADQUARTERS, access_level=AccessLevel.LEVEL_2)
        self.assertEqual(
            user.capabilities,
            frozenset(
                {Capability.CREATE_DOCUMENT, Capability.CONFIRM_DOCUMENT, Capability.PRINT_DOCUMENT}
            ),
        )

    def test_employer_approves_and_manages_personnel_but_does_not_author(self):
        user = User(access_roll=AccessRoll.EMPLOYER, access_level=AccessLevel.LEVEL_1)
        self.assertEqual(
            user.capabilities,
            frozenset(
                {Capability.APPROVE_DOCUMENT, Capability.MANAGE_PERSONNEL, Capability.PRINT_DOCUMENT}
            ),
        )
        # Separation of duties: the approver must not be able to author.
        self.assertFalse(user.has_capability(Capability.CREATE_DOCUMENT))
        self.assertFalse(user.has_capability(Capability.CONFIRM_DOCUMENT))

    def test_no_single_roll_can_take_a_document_end_to_end(self):
        for roll in AccessRoll.values:
            user = User(access_roll=roll, access_level=AccessLevel.LEVEL_1)
            full_chain = {
                Capability.CREATE_DOCUMENT,
                Capability.CONFIRM_DOCUMENT,
                Capability.APPROVE_DOCUMENT,
            }
            self.assertFalse(full_chain.issubset(user.capabilities), roll)

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
        self.assertEqual(
            response.data["capabilities"], [Capability.CREATE_DOCUMENT, Capability.PRINT_DOCUMENT]
        )

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
