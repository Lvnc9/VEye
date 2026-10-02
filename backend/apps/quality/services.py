"""Every write to the quality module goes through here (Phase 18) — the one place that records an event.

The shape is the workflow's: **lock the row, check who may, check the status, write, record the event**
— all in one transaction, so two people acting at once cannot both win and a refused change leaves no
line in the history. Who may is decided in `access.py`; the checks are repeated here, not left to the
views, because the rule must hold whoever calls.
"""
import datetime

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.core.exceptions import ConflictError
from apps.core.text import normalize_title
from apps.documents.authority import approve_eligible_users
from apps.notifications import services as notifications
from apps.notifications.models import NotificationKind
from apps.organization.access import OrgAccess, users_leading_at_or_above
from apps.organization.models import OrgNode
from apps.organization.tree import lock_node

from .access import NOT_A_MANAGER, can_manage, can_report, require_manager
from .models import NcSeverity, NcSource, NcStatus, NonConformance, QualityEvent, QualityEventKind

TITLE_MAX = 255
TEXT_MAX = 4000

#: What an edit may touch, and how it reads in the history line.
EDITABLE_FIELDS = {
    "title": "عنوان",
    "description": "شرح",
    "source": "منبع",
    "severity": "شدت",
    "owner_node": "گره مسئول",
    "related_document": "مستند مرتبط",
    "detected_on": "تاریخ کشف",
}


def record_event(kind, actor, *, nc=None, **extra) -> QualityEvent:
    """One line of the history. The actor's name and سمت are snapshotted as text."""
    return QualityEvent.objects.create(
        nc=nc,
        kind=kind,
        actor=actor,
        actor_name=actor.full_name if actor else "",
        actor_title=actor.title if actor else "",
        **extra,
    )


def _clean_text(value, field: str, *, max_length: int, required: bool = True) -> str:
    text = (value or "").strip()
    if required and not text:
        raise ValidationError({field: ["این فیلد الزامی است."]})
    if len(text) > max_length:
        raise ValidationError({field: [f"نباید بیش از {max_length} نویسه باشد."]})
    return text


def _lock(pk: int) -> NonConformance:
    try:
        return NonConformance.objects.select_for_update().select_related("owner_node", "reported_by").get(pk=pk)
    except NonConformance.DoesNotExist:
        raise NotFound("عدم‌انطباق یافت نشد.")


def _require_status(nc: NonConformance, expected, verb: str) -> None:
    allowed = (expected,) if isinstance(expected, str) else tuple(expected)
    if nc.status not in allowed:
        raise ConflictError(
            f"این مورد در وضعیت «{nc.get_status_display()}» است و نمی‌توان آن را {verb}.",
            code="wrong_status",
            status=nc.status,
        )


def _require_active_node(node: OrgNode) -> None:
    if not node.is_active:
        raise ConflictError(
            "برای گرهٔ بایگانی‌شده نمی‌توان عدم‌انطباق ثبت کرد.", code="node_archived", node_id=node.pk
        )


def _triagers(node: OrgNode, actor):
    """Whom to tell about a new report: the مسئولان of the node and above; with nobody leading, the
    مدیر عامل (the same fallback a document with no owner node has)."""
    people = list(users_leading_at_or_above(node)) or list(approve_eligible_users())
    return [person for person in people if person.pk != getattr(actor, "pk", None)]


# -- report and edit ---------------------------------------------------------


@transaction.atomic
def report(
    *, actor, title, description, owner_node, source=NcSource.INTERNAL, severity=NcSeverity.MINOR,
    detected_on=None, related_document=None,
) -> NonConformance:
    """Anyone may report one. It needs an *active* node — whose process this is — but no authority
    over it: a person who sees a problem in another unit is exactly who should be able to say so."""
    if not can_report(actor):
        raise PermissionDenied("این حساب نمی‌تواند عدم‌انطباق ثبت کند.")
    title = normalize_title(_clean_text(title, "title", max_length=TITLE_MAX))
    description = _clean_text(description, "description", max_length=TEXT_MAX)
    today = timezone.localdate()
    detected_on = detected_on or today
    if detected_on > today:
        raise ValidationError({"detected_on": ["تاریخ کشف نمی‌تواند در آینده باشد."]})
    node = lock_node(owner_node.pk)
    _require_active_node(node)

    nc = NonConformance.objects.create(
        title=title, description=description, source=source, severity=severity, owner_node=node,
        reported_by=actor, detected_on=detected_on, related_document=related_document,
    )
    record_event(
        QualityEventKind.NC_REPORTED, actor, nc=nc, subject_title=nc.title, to_status=NcStatus.OPEN
    )
    notifications.notify_many(
        _triagers(node, actor),
        kind=NotificationKind.NC_REPORTED,
        title=f"«{nc.code}» ثبت شد: {nc.title}",
        body=node.name,
        url=f"/quality/{nc.pk}",
    )
    return nc


@transaction.atomic
def edit(nc: NonConformance, *, actor, changes: dict) -> NonConformance:
    """The reporter may correct their own report **while it is still OPEN**; a manager may until it is
    closed. Closed and rejected records are read-only until reopened. Only real changes are recorded."""
    nc = _lock(nc.pk)
    manager = can_manage(OrgAccess(actor), nc.owner_node)
    reporter_window = nc.reported_by_id == actor.pk and nc.status == NcStatus.OPEN
    if nc.status not in (NcStatus.OPEN, NcStatus.IN_PROGRESS):
        raise ConflictError(
            f"این مورد در وضعیت «{nc.get_status_display()}» است و فقط‌خواندنی است. ابتدا آن را بازگشایی کنید.",
            code="wrong_status",
            status=nc.status,
        )
    if not (manager or reporter_window):
        raise PermissionDenied(NOT_A_MANAGER)

    unknown = set(changes) - set(EDITABLE_FIELDS)
    if unknown:
        raise ValidationError({name: ["این فیلد قابل ویرایش نیست."] for name in sorted(unknown)})
    cleaned = dict(changes)
    if "title" in cleaned:
        cleaned["title"] = normalize_title(_clean_text(cleaned["title"], "title", max_length=TITLE_MAX))
    if "description" in cleaned:
        cleaned["description"] = _clean_text(cleaned["description"], "description", max_length=TEXT_MAX)
    if "detected_on" in cleaned and cleaned["detected_on"] > timezone.localdate():
        raise ValidationError({"detected_on": ["تاریخ کشف نمی‌تواند در آینده باشد."]})
    if "owner_node" in cleaned and cleaned["owner_node"].pk != nc.owner_node_id:
        node = lock_node(cleaned["owner_node"].pk)
        _require_active_node(node)
        # Handing it to another unit needs authority there too (a reporter fixing their own OPEN
        # report is the exception — they needed none to file it).
        if not reporter_window and not can_manage(OrgAccess(actor), node):
            raise PermissionDenied("برای انتقال باید مسئول گرهٔ مقصد (یا گره‌های بالادست آن) هم باشید.")
        cleaned["owner_node"] = node

    changed = []
    for name, value in cleaned.items():
        current = getattr(nc, name)
        same = (current.pk == value.pk) if hasattr(current, "pk") and value is not None else current == value
        if not same:
            setattr(nc, name, value)
            changed.append(name)
    if not changed:
        return nc
    nc.save(update_fields=[*changed, "updated_at"])
    record_event(
        QualityEventKind.NC_EDITED, actor, nc=nc, subject_title=nc.title,
        note="، ".join(EDITABLE_FIELDS[name] for name in changed),
    )
    return nc


# -- triage ------------------------------------------------------------------


def _tell_reporter(nc: NonConformance, actor, kind, title: str, body: str = "") -> None:
    if nc.reported_by_id != actor.pk:
        notifications.notify(nc.reported_by, kind=kind, title=title, body=body, url=f"/quality/{nc.pk}")


@transaction.atomic
def accept(nc: NonConformance, *, actor, root_cause, severity=None) -> NonConformance:
    """Triage: this is a real problem, here is why it happened. The root cause is required — a record
    nobody has asked «why?» of is not ready for anyone to fix."""
    nc = _lock(nc.pk)
    require_manager(actor, nc.owner_node)
    _require_status(nc, NcStatus.OPEN, "پذیرفت")
    nc.root_cause = _clean_text(root_cause, "root_cause", max_length=TEXT_MAX)
    if severity:
        nc.severity = severity
    nc.status = NcStatus.IN_PROGRESS
    nc.accepted_at = timezone.now()
    nc.save(update_fields=["root_cause", "severity", "status", "accepted_at", "updated_at"])
    record_event(
        QualityEventKind.NC_ACCEPTED, actor, nc=nc, subject_title=nc.title,
        from_status=NcStatus.OPEN, to_status=NcStatus.IN_PROGRESS,
    )
    _tell_reporter(nc, actor, NotificationKind.NC_ACCEPTED, f"«{nc.code}» پذیرفته شد", nc.title)
    return nc


@transaction.atomic
def reject(nc: NonConformance, *, actor, reason) -> NonConformance:
    """Triage: this is not a non-conformance. The reason is required and stays on the record."""
    nc = _lock(nc.pk)
    require_manager(actor, nc.owner_node)
    _require_status(nc, NcStatus.OPEN, "رد کرد")
    nc.rejection_reason = _clean_text(reason, "reason", max_length=TEXT_MAX)
    nc.status = NcStatus.REJECTED
    nc.save(update_fields=["rejection_reason", "status", "updated_at"])
    record_event(
        QualityEventKind.NC_REJECTED, actor, nc=nc, subject_title=nc.title,
        from_status=NcStatus.OPEN, to_status=NcStatus.REJECTED, note=nc.rejection_reason,
    )
    _tell_reporter(nc, actor, NotificationKind.NC_REJECTED, f"«{nc.code}» رد شد", nc.rejection_reason)
    return nc


@transaction.atomic
def reopen(nc: NonConformance, *, actor, reason) -> NonConformance:
    """A rejected report goes back to triage (OPEN) — not straight to «در دست اقدام», which would skip
    the root cause the accept step demands."""
    nc = _lock(nc.pk)
    require_manager(actor, nc.owner_node)
    _require_status(nc, NcStatus.REJECTED, "بازگشایی کرد")
    reason = _clean_text(reason, "reason", max_length=TEXT_MAX)
    nc.status = NcStatus.OPEN
    nc.rejection_reason = ""
    nc.save(update_fields=["status", "rejection_reason", "updated_at"])
    record_event(
        QualityEventKind.NC_REOPENED, actor, nc=nc, subject_title=nc.title,
        from_status=NcStatus.REJECTED, to_status=NcStatus.OPEN, note=reason,
    )
    return nc
