"""First-run bootstrap, run entirely by the developer account (Phase 10, ADR-010, decided with the
owner 2026-09-25). No setup token, and no مدیر عامل is created here at all — that person is
registered afterwards as ordinary personnel, through the wizard's «پرسنل» step (A4's `POST
/personnel/`).

Two doors, both race-safe the same way (an insert that can fail, not a locked read of rows that do
not exist yet):

* `POST /setup/bootstrap/` (anonymous, rate-limited) creates the **one** developer account:
  `User.is_developer=True`, صفی / لول ۳, never `is_superuser`, no membership, no company. Guarded
  by `uniq_developer_account` (a partial unique constraint on `is_developer`) — two concurrent
  bootstraps both try to insert a developer; the loser blocks on that index until the winner
  commits, then fails, which `bootstrap_developer()` turns into 409 `developer_exists` and rolls
  the loser's user back with it. A duplicate national code is likewise a 409 with nothing kept.
* `POST /setup/start/` (the developer's own session) creates the root `OrgNode`, its channel and
  `Company(pk=1)` — and deliberately **no membership**: the developer itself may never sit in the
  chart. Guarded the same way, by `Company(pk=1)`'s primary key (and, one insert earlier, by the
  root's own `uniq_company_root_node`).

`POST /setup/complete/` now needs a fact about the *chart*, not a stored roll: an active lead
Membership on the company root (someone the wizard's «پرسنل» step placed as «مسئول» at «خود
شرکت»). Until then it is 409 `root_lead_missing`.
"""
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.accounts.models import AccessLevel, AccessRoll
from apps.core.exceptions import ConflictError

from . import tree
from .models import Company, Membership, SetupStep

User = get_user_model()

#: Constraint names whose violation means "someone else already took this seat".
_DEVELOPER_UNIQUE = "uniq_developer_account"
_COMPANY_UNIQUE = {"uniq_company_root_node", "organization_company_pkey"}
_NATIONAL_CODE_UNIQUE = "accounts_user_national_code_key"


def _developer_exists() -> ConflictError:
    return ConflictError("حساب توسعه‌دهنده از قبل ساخته شده است.", code="developer_exists")


def _already_bootstrapped() -> ConflictError:
    return ConflictError("راه‌اندازی شرکت قبلاً انجام شده است.", code="already_bootstrapped")


def _national_code_exists() -> ConflictError:
    return ConflictError("کاربری با این کد ملی وجود دارد.", code="national_code_exists")


def _root_lead_missing() -> ConflictError:
    return ConflictError(
        "برای پایان راه‌اندازی، دست‌کم یک «مسئول» باید در ریشهٔ ساختار سازمان ثبت شده باشد.",
        code="root_lead_missing",
    )


def _constraint_name(exc: IntegrityError) -> str | None:
    return getattr(getattr(exc.__cause__, "diag", None), "constraint_name", None)


def bootstrap_developer(*, full_name: str, national_code: str, mobile_phone: str, password: str) -> "User":
    try:
        return _bootstrap_developer(full_name, national_code, mobile_phone, password)
    except IntegrityError as exc:  # raised after the transaction below rolled back
        constraint = _constraint_name(exc)
        if constraint == _DEVELOPER_UNIQUE:
            raise _developer_exists()
        if constraint == _NATIONAL_CODE_UNIQUE:
            raise _national_code_exists()
        raise


@transaction.atomic
def _bootstrap_developer(full_name, national_code, mobile_phone, password) -> "User":
    if User.objects.filter(is_developer=True).exists():
        raise _developer_exists()
    if User.objects.filter(national_code=national_code).exists():
        raise _national_code_exists()
    return User.objects.create_user(
        national_code=national_code,
        password=password,
        full_name=full_name,
        mobile_phone=mobile_phone,
        access_roll=AccessRoll.GUILD,
        access_level=AccessLevel.LEVEL_3,
        is_developer=True,
    )


def start_company(*, company_name: str) -> Company:
    try:
        return _start_company(company_name)
    except IntegrityError as exc:
        if _constraint_name(exc) in _COMPANY_UNIQUE:
            raise _already_bootstrapped()
        raise


@transaction.atomic
def _start_company(company_name) -> Company:
    if Company.objects.exists():
        raise _already_bootstrapped()
    root = tree.create_root(name=company_name)  # the root's own channel is made in the same transaction
    return Company.objects.create(pk=1, root=root, setup_step=SetupStep.DOMAINS)


def has_root_lead() -> bool:
    """An active lead Membership sits on the company root — the fact «پایان راه‌اندازی» waits for."""
    company = Company.objects.only("root_id").first()
    if company is None:
        return False
    return Membership.objects.filter(node_id=company.root_id, is_lead=True, user__is_active=True).exists()


def complete_setup() -> None:
    """Finish the wizard. One conditional UPDATE, not read-then-write: of two concurrent callers
    exactly one changes a row, and the other is told it was already done."""
    if not Company.objects.exists():
        raise NotFound("شرکت هنوز راه‌اندازی نشده است.")
    if not has_root_lead():
        raise _root_lead_missing()
    now = timezone.now()
    changed = Company.objects.filter(pk=1, setup_completed_at__isnull=True).update(
        setup_completed_at=now, setup_step=SetupStep.DONE, updated_at=now
    )
    if changed == 0:
        raise ConflictError("راه‌اندازی قبلاً به پایان رسیده است.", code="already_completed")


def setup_status() -> dict:
    """What the public landing page and the login page may learn, and nothing more: no counts, no
    names, never whether a given national code exists."""
    company = Company.objects.only("setup_step", "setup_completed_at").first()
    return {
        "developer_exists": User.objects.filter(is_developer=True).exists(),
        "company_exists": company is not None,
        "completed": bool(company and company.setup_completed_at),
        "step": company.setup_step if company else None,
        "has_root_lead": has_root_lead(),
    }
