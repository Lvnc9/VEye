"""First-run bootstrap: from an empty database to a company with a مدیر عامل.

**Is the database fresh?** `not Company.objects.exists()` — *not* "are there no users": the V_1.0
importer creates an inactive `import_user` and personnel may exist already. The Company row is
the only honest marker.

**The race-safe first write** is one transaction (`_bootstrap`):

    1. fast path: a Company already exists            -> 409 already_bootstrapped (for the message)
    2. the root OrgNode
    3. Company(pk=1)                                  <- THE GUARD
    4. the manager: a new User, or an existing one promoted
    5. the manager's lead + primary membership on the root

Step 3 is what makes this impossible to run twice. Two concurrent bootstraps both try to insert
Company(pk=1) (and, before it, a second COMPANY root); the loser blocks on that unique index until
the winner commits, then fails, which `bootstrap()` turns into 409 and rolls back the loser's root
node and user with it. The `if` at step 1 exists for the error message; the constraints exist for
the correctness. (A `select_for_update` on the users table would not work: Postgres cannot lock
rows that do not exist yet.) A duplicate national code is likewise a 409 with everything rolled
back — no half-bootstrapped state is reachable.

The manager is کارفرمایی / لول ۱ with no choice offered, so they inherit every capability through
`FULL_ACCESS_POSITIONS`, present and future. `is_superuser` is deliberately not set: that is a
Django-admin concept, and the roll already grants everything in-app.

**No setup token** (removed by the owner, 2026-09-25). Two doors instead:

* `POST /setup/bootstrap/` (anonymous) *creates* the first مدیر عامل — only while no active
  کارفرمایی / لول ۱ exists, else 409 `manager_exists`. Until setup is done on a fresh install,
  whoever reaches the server first can take that seat; the owner accepted this.
* `POST /setup/start/` (signed in) promotes the caller *themselves* through the path below.

**Promoting an existing manager** (the importer path, where users exist but no Company) never sets
or reads a password, and it is reachable only from that manager's own session (`setup/start/`), so
it issues no new session either.
"""
from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.accounts.models import AccessLevel, AccessRoll
from apps.core.exceptions import ConflictError

from . import memberships, tree
from .models import Company, SetupStep

User = get_user_model()

#: Constraints whose violation means "someone else bootstrapped first".
_ALREADY_BOOTSTRAPPED = {"uniq_company_root_node", "organization_company_pkey"}
_NATIONAL_CODE_UNIQUE = "accounts_user_national_code_key"

#: Who may be the company's مدیر عامل: an active کارفرمایی / لول ۱ — never the importer's inactive
#: `import_user`.
_MANAGER = {"is_active": True, "access_roll": AccessRoll.EMPLOYER, "access_level": AccessLevel.LEVEL_1}


@dataclass(frozen=True)
class BootstrapResult:
    company: Company
    user: "User"
    created_user: bool


def _already_bootstrapped() -> ConflictError:
    return ConflictError("راه‌اندازی اولیه قبلاً انجام شده است.", code="already_bootstrapped")


def _manager_exists() -> ConflictError:
    return ConflictError(
        "حساب مدیر عامل از قبل وجود دارد؛ با آن وارد شوید و «شروع راه‌اندازی» را بزنید.", code="manager_exists"
    )


def _national_code_exists() -> ConflictError:
    return ConflictError("کاربری با این کد ملی وجود دارد.", code="national_code_exists")


def _constraint_name(exc: IntegrityError) -> str | None:
    return getattr(getattr(exc.__cause__, "diag", None), "constraint_name", None)


def bootstrap(*, company_name: str, manager: dict | None = None, existing_manager_national_code: str | None = None) -> BootstrapResult:
    """Exactly one of `manager` (create this person) or `existing_manager_national_code`
    (promote them) must be given."""
    if (manager is None) == (existing_manager_national_code is None):
        raise ValueError("pass exactly one of manager / existing_manager_national_code")
    try:
        return _bootstrap(company_name, manager, existing_manager_national_code)
    except IntegrityError as exc:  # raised after _bootstrap's transaction rolled back
        constraint = _constraint_name(exc)
        if constraint in _ALREADY_BOOTSTRAPPED:
            raise _already_bootstrapped()
        if constraint == _NATIONAL_CODE_UNIQUE:
            raise _national_code_exists()
        raise


@transaction.atomic
def _bootstrap(company_name, manager, existing_national_code) -> BootstrapResult:
    if Company.objects.exists():
        raise _already_bootstrapped()

    if existing_national_code is not None:
        user = _eligible_manager(existing_national_code)
    elif User.objects.filter(**_MANAGER).exists():
        raise _manager_exists()  # an anonymous form must not mint a second مدیر عامل
    elif User.objects.filter(national_code=manager["national_code"]).exists():
        raise _national_code_exists()

    root = tree.create_root(name=company_name)
    company = Company.objects.create(pk=1, root=root, setup_step=SetupStep.DOMAINS)  # the guard

    created = existing_national_code is None
    if created:
        user = User.objects.create_user(
            national_code=manager["national_code"],
            password=manager["password"],
            full_name=manager["full_name"],
            mobile_phone=manager.get("mobile_phone", ""),
            access_roll=AccessRoll.EMPLOYER,
            access_level=AccessLevel.LEVEL_1,
        )
    memberships.add_membership(
        user=user, node=root, is_lead=True, is_primary=True, added_by=user, advance_setup=False
    )
    return BootstrapResult(company=company, user=user, created_user=created)


def _eligible_manager(national_code: str):
    """An active کارفرمایی / لول ۱ — never the importer's inactive `import_user`. One answer for
    "no such person" and "not eligible", so it says nothing about which national codes exist."""
    user = User.objects.select_for_update().filter(national_code=national_code, **_MANAGER).first()
    if user is None:
        raise ConflictError(
            "این کد ملی متعلق به یک مدیر عامل فعال نیست.", code="manager_not_eligible"
        )
    return user


def is_eligible_manager(user) -> bool:
    """The signed-in side of the same rule `_eligible_manager` applies inside the transaction."""
    return all(getattr(user, field, None) == value for field, value in _MANAGER.items())


def complete_setup() -> None:
    """Finish the wizard. One conditional UPDATE, not read-then-write: of two concurrent callers
    exactly one changes a row, and the other is told it was already done."""
    if not Company.objects.exists():
        raise NotFound("شرکت هنوز راه‌اندازی نشده است.")
    now = timezone.now()
    changed = Company.objects.filter(pk=1, setup_completed_at__isnull=True).update(
        setup_completed_at=now, setup_step=SetupStep.DONE, updated_at=now
    )
    if changed == 0:
        raise ConflictError("راه‌اندازی قبلاً به پایان رسیده است.", code="already_completed")


def setup_status() -> dict:
    """What the public login page may learn, and nothing more: no counts, no names, never whether a
    given national code exists.

    `has_users` means "an active کارفرمایی / لول ۱ account exists": the anonymous form is then closed
    (409 `manager_exists`) and that person signs in instead — the importer's inactive `import_user`
    does not count.
    """
    company = Company.objects.only("setup_step").first()
    return {
        "needed": company is None,
        "has_users": User.objects.filter(**_MANAGER).exists(),
        "step": company.setup_step if company else None,
    }
