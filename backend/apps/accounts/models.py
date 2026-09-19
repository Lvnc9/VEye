from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models


class AccessRoll(models.TextChoices):
    """V_1.0: other_folder/register.py:392-409 (the نوع دسترسی dropdown)."""

    EMPLOYER = "EMPLOYER", "کارفرمایی"
    HEADQUARTERS = "HEADQUARTERS", "ستادی"
    GUILD = "GUILD", "صفی"


class AccessLevel(models.TextChoices):
    """V_1.0: other_folder/register.py:365-382 (the سطح دسترسی dropdown)."""

    LEVEL_1 = "L1", "لول ۱"
    LEVEL_2 = "L2", "لول ۲"
    LEVEL_3 = "L3", "لول ۳"


class Capability(models.TextChoices):
    """Domain-level capabilities, as opposed to Django's per-model CRUD
    permissions. Deliberately kept as a single computed source of truth on
    User rather than mirrored into Django Groups, which would be a second
    place for the policy to drift.
    """

    CREATE_DOCUMENT = "create_document", "تدوین مستند"
    CONFIRM_DOCUMENT = "confirm_document", "تایید مستند"
    APPROVE_DOCUMENT = "approve_document", "تصویب مستند"
    MANAGE_PERSONNEL = "manage_personnel", "مدیریت پرسنل"


#: Access roll -> capabilities. See User.capabilities for the rationale.
#: MANAGE_PERSONNEL sits with کارفرمایی because V_1.0 surfaced the personnel
#: buttons on the dashboard of the مدیر عامل (Dashboard.py:241-246).
ROLL_CAPABILITIES = {
    AccessRoll.GUILD: frozenset({Capability.CREATE_DOCUMENT}),
    AccessRoll.HEADQUARTERS: frozenset({Capability.CREATE_DOCUMENT, Capability.CONFIRM_DOCUMENT}),
    AccessRoll.EMPLOYER: frozenset({Capability.APPROVE_DOCUMENT, Capability.MANAGE_PERSONNEL}),
}


class UserManager(BaseUserManager):
    """Custom manager, required since User is not Django's default
    username/email-based model (USERNAME_FIELD = national_code)."""

    use_in_migrations = True

    def _create_user(self, national_code, password, **extra_fields):
        if not national_code:
            raise ValueError("national_code is required")
        user = self.model(national_code=national_code, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, national_code, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("access_roll", AccessRoll.GUILD)
        extra_fields.setdefault("access_level", AccessLevel.LEVEL_3)
        return self._create_user(national_code, password, **extra_fields)

    def create_superuser(self, national_code, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("access_roll", AccessRoll.EMPLOYER)
        extra_fields.setdefault("access_level", AccessLevel.LEVEL_1)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(national_code, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Personnel / RBAC, per skeleton.md §3 — replaces V1's hardcoded
    {"root": "1234"} account dict (register.py)."""

    national_code = models.CharField(max_length=32, unique=True)
    full_name = models.CharField(max_length=255)
    mobile_phone = models.CharField(max_length=32, blank=True)
    access_roll = models.CharField(max_length=16, choices=AccessRoll.choices)
    access_level = models.CharField(max_length=8, choices=AccessLevel.choices)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "national_code"
    REQUIRED_FIELDS = ["full_name", "access_roll", "access_level"]

    # Fixed 3x3 Access Roll x Access Level -> Title matrix, ported verbatim
    # from V_1.0 other_folder/register.py:739-769.
    TITLE_MATRIX = {
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

    class Meta:
        ordering = ["national_code"]

    def __str__(self):
        return f"{self.full_name} ({self.national_code})"

    @property
    def title(self) -> str:
        return self.TITLE_MATRIX[(self.access_roll, self.access_level)]

    @property
    def capabilities(self) -> frozenset[str]:
        """Domain capabilities granted by this user's access roll.

        V_1.0 had no enforcement at all — the role matrix only printed a
        label, and any user at the keyboard could fill in any of the four
        sign-off panels. This is the policy that replaces that, confirmed
        with the product owner:

            تدوین (create)  -> صفی، ستادی
            تایید (confirm) -> ستادی
            تصویب (approve) -> کارفرمایی

        Separation of duties is deliberate: کارفرمایی approves but does not
        author, so no single roll can take a document end to end.
        """
        if self.is_superuser:
            return frozenset(Capability.values)
        return ROLL_CAPABILITIES.get(self.access_roll, frozenset())

    def has_capability(self, capability: str) -> bool:
        return capability in self.capabilities
