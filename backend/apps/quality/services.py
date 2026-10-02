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
from .models import (
    FINAL_ACTION_STATUSES,
    ActionStatus,
    CorrectiveAction,
    NcSeverity,
    NcSource,
    NcStatus,
    NonConformance,
    QualityEvent,
    QualityEventKind,
)

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


def _chain_leads(node: OrgNode, *skip):
    """The مسئولان of `node` and every node above it; with nobody leading, the مدیر عامل (the same
    fallback a document with no owner node has). `skip` are people not to tell — whoever just acted,
    and for a verification, the person who did the work."""
    people = list(users_leading_at_or_above(node)) or list(approve_eligible_users())
    excluded = {person.pk for person in skip if person is not None}
    return [person for person in people if person.pk not in excluded]


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
        _chain_leads(node, actor),
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
    """Undo a decision. A **rejected** report goes back to triage (OPEN) — not straight to «در دست
    اقدام», which would skip the root cause the accept step demands. A **closed** record goes back to
    IN_PROGRESS: its verified actions stay verified, and the effectiveness note is cleared from the
    record (the closing line in the history keeps it) so it never reads as true of a record that is
    open again."""
    nc = _lock(nc.pk)
    require_manager(actor, nc.owner_node)
    _require_status(nc, (NcStatus.REJECTED, NcStatus.CLOSED), "بازگشایی کرد")
    reason = _clean_text(reason, "reason", max_length=TEXT_MAX)
    came_from = nc.status
    if came_from == NcStatus.REJECTED:
        nc.status, nc.rejection_reason = NcStatus.OPEN, ""
        fields = ["status", "rejection_reason", "updated_at"]
    else:
        nc.status, nc.closed_at, nc.closed_by, nc.effectiveness_note = NcStatus.IN_PROGRESS, None, None, ""
        fields = ["status", "closed_at", "closed_by", "effectiveness_note", "updated_at"]
    nc.save(update_fields=fields)
    record_event(
        QualityEventKind.NC_REOPENED, actor, nc=nc, subject_title=nc.title,
        from_status=came_from, to_status=nc.status, note=reason,
    )
    return nc


@transaction.atomic
def close(nc: NonConformance, *, actor, effectiveness_note) -> NonConformance:
    """The rule the owner chose (2026-10-02): **at least one action, every non-cancelled action
    verified, and a written effectiveness note** — the fix was done, someone else checked it, and
    someone wrote down why it worked. A report that is not real is *rejected* at triage, never closed.
    Checked under the row lock, so a verification failing at the same moment cannot slip past it."""
    nc = _lock(nc.pk)
    require_manager(actor, nc.owner_node)
    _require_status(nc, NcStatus.IN_PROGRESS, "بست")
    live = nc.actions.exclude(status=ActionStatus.CANCELLED)
    total = live.count()
    verified = live.filter(status=ActionStatus.VERIFIED).count()
    if total == 0:
        raise ConflictError(
            "برای بستن، دست‌کم یک اقدام اصلاحی لازم است. اگر این مورد واقعی نیست، آن را رد کنید.",
            code="cannot_close", actions=0, verified=0, unverified=0,
        )
    if verified < total:
        raise ConflictError(
            f"{total - verified} اقدام هنوز تایید نشده است.",
            code="cannot_close", actions=total, verified=verified, unverified=total - verified,
        )
    nc.effectiveness_note = _clean_text(effectiveness_note, "effectiveness_note", max_length=TEXT_MAX)
    nc.status, nc.closed_at, nc.closed_by = NcStatus.CLOSED, timezone.now(), actor
    nc.save(update_fields=["effectiveness_note", "status", "closed_at", "closed_by", "updated_at"])
    record_event(
        QualityEventKind.NC_CLOSED, actor, nc=nc, subject_title=nc.title,
        from_status=NcStatus.IN_PROGRESS, to_status=NcStatus.CLOSED, note=nc.effectiveness_note,
    )
    people = {nc.reported_by_id: nc.reported_by}
    for action in live.select_related("assignee"):
        people[action.assignee_id] = action.assignee
    people.pop(actor.pk, None)
    notifications.notify_many(
        people.values(), kind=NotificationKind.NC_CLOSED, title=f"«{nc.code}» بسته شد",
        body=nc.title, url=f"/quality/{nc.pk}",
    )
    return nc


# -- corrective actions --------------------------------------------------------

#: Where an action may go by the assignee's (or a manager's) hand. VERIFIED and CANCELLED are reached
#: only through `verify_action` / `cancel_action`; VERIFIED is left only by reopening the record.
STATUS_GRAPH = {
    ActionStatus.TODO: {ActionStatus.IN_PROGRESS},
    ActionStatus.IN_PROGRESS: {ActionStatus.TODO, ActionStatus.DONE},
    ActionStatus.DONE: {ActionStatus.IN_PROGRESS},
}
ACTION_EDITABLE = {"title": "عنوان", "description": "شرح", "assignee": "مسئول اقدام", "due_on": "مهلت", "status": "وضعیت"}


def _lock_action(nc: NonConformance, pk: int) -> CorrectiveAction:
    try:
        return CorrectiveAction.objects.select_for_update().select_related("assignee").get(pk=pk, nc_id=nc.pk)
    except CorrectiveAction.DoesNotExist:
        raise NotFound("اقدام یافت نشد.")


def _require_in_progress(nc: NonConformance) -> None:
    if nc.status != NcStatus.IN_PROGRESS:
        raise ConflictError(
            "اقدام‌ها فقط وقتی عدم‌انطباق «در دست اقدام» است قابل تغییرند.",
            code="nc_not_in_progress", status=nc.status,
        )


def _require_not_final(action: CorrectiveAction) -> None:
    if action.status in FINAL_ACTION_STATUSES:
        raise ConflictError(
            f"این اقدام «{action.get_status_display()}» است و دیگر تغییر نمی‌کند.",
            code="wrong_status", status=action.status,
        )


def _require_eligible(user) -> None:
    if not user.is_active or user.is_developer:
        raise ConflictError("این شخص نمی‌تواند مسئول اقدام شود.", code="assignee_not_eligible", user_id=user.pk)


def _require_future(due_on: datetime.date) -> None:
    if due_on < timezone.localdate():
        raise ConflictError("مهلت نمی‌تواند در گذشته باشد.", code="due_in_past")


def _tell(person, actor, kind, nc: NonConformance, title: str, body: str = "") -> None:
    if person.pk != actor.pk:
        notifications.notify(person, kind=kind, title=title, body=body, url=f"/quality/{nc.pk}")


@transaction.atomic
def add_action(nc: NonConformance, *, actor, title, assignee, due_on, description="") -> CorrectiveAction:
    nc = _lock(nc.pk)
    require_manager(actor, nc.owner_node)
    _require_in_progress(nc)
    title = normalize_title(_clean_text(title, "title", max_length=TITLE_MAX))
    description = _clean_text(description, "description", max_length=TEXT_MAX, required=False)
    _require_eligible(assignee)
    _require_future(due_on)
    action = CorrectiveAction.objects.create(
        nc=nc, title=title, description=description, assignee=assignee, due_on=due_on
    )
    record_event(
        QualityEventKind.ACTION_ADDED, actor, nc=nc, action=action, subject_title=action.title,
        note=assignee.full_name,
    )
    _tell(assignee, actor, NotificationKind.CAPA_ASSIGNED, nc, f"اقدام «{action.title}» به شما واگذار شد", f"{nc.code}: {nc.title}")
    return action


@transaction.atomic
def update_action(nc: NonConformance, action: CorrectiveAction, *, actor, changes: dict) -> CorrectiveAction:
    """The assignee may change **the status, and only the status** (the objective-assignee rule); title,
    description, assignee and deadline are the manager's. A request mixing both needs the manager."""
    nc = _lock(nc.pk)
    action = _lock_action(nc, action.pk)
    _require_in_progress(nc)
    _require_not_final(action)
    manager = can_manage(OrgAccess(actor), nc.owner_node)
    status_only = set(changes) <= {"status"}
    if not (manager or (action.assignee_id == actor.pk and status_only)):
        raise PermissionDenied(
            NOT_A_MANAGER if not status_only else "فقط مسئول این اقدام یا مسئول عدم‌انطباق می‌تواند وضعیت آن را تغییر دهد."
        )
    unknown = set(changes) - set(ACTION_EDITABLE)
    if unknown:
        raise ValidationError({name: ["این فیلد قابل ویرایش نیست."] for name in sorted(unknown)})

    edited = []
    if "title" in changes:
        title = normalize_title(_clean_text(changes["title"], "title", max_length=TITLE_MAX))
        if title != action.title:
            action.title = title
            edited.append("title")
    if "description" in changes:
        description = _clean_text(changes["description"], "description", max_length=TEXT_MAX, required=False)
        if description != action.description:
            action.description = description
            edited.append("description")
    if edited:
        action.save(update_fields=[*edited, "updated_at"])
        record_event(
            QualityEventKind.ACTION_EDITED, actor, nc=nc, action=action, subject_title=action.title,
            note="، ".join(ACTION_EDITABLE[name] for name in edited),
        )
    if "assignee" in changes and changes["assignee"].pk != action.assignee_id:
        new = changes["assignee"]
        _require_eligible(new)
        old_name = action.assignee.full_name
        action.assignee = new
        action.save(update_fields=["assignee", "updated_at"])
        record_event(
            QualityEventKind.ACTION_ASSIGNED, actor, nc=nc, action=action, subject_title=action.title,
            note=f"{old_name} ← {new.full_name}",
        )
        _tell(new, actor, NotificationKind.CAPA_ASSIGNED, nc, f"اقدام «{action.title}» به شما واگذار شد", f"{nc.code}: {nc.title}")
    if "due_on" in changes and changes["due_on"] != action.due_on:
        _require_future(changes["due_on"])
        old = action.due_on
        action.due_on = changes["due_on"]
        action.save(update_fields=["due_on", "updated_at"])
        record_event(
            QualityEventKind.ACTION_DUE_CHANGED, actor, nc=nc, action=action, subject_title=action.title,
            from_status=old.isoformat(), to_status=action.due_on.isoformat(),
        )
    if "status" in changes and changes["status"] != action.status:
        _move_status(nc, action, actor, changes["status"])
    return action


def _move_status(nc: NonConformance, action: CorrectiveAction, actor, new: str) -> None:
    old = action.status
    if new not in STATUS_GRAPH.get(old, ()):
        raise ConflictError(
            f"از «{ActionStatus(old).label}» نمی‌توان به «{ActionStatus(new).label}» رفت.",
            code="invalid_transition", from_status=old, to_status=new,
        )
    action.status = new
    action.completed_at = timezone.now() if new == ActionStatus.DONE else None
    action.save(update_fields=["status", "completed_at", "updated_at"])
    record_event(
        QualityEventKind.ACTION_STATUS_CHANGED, actor, nc=nc, action=action, subject_title=action.title,
        from_status=old, to_status=new,
    )
    if new == ActionStatus.DONE:
        # Never the person who did the work — they may not verify it, so telling them would be noise.
        notifications.notify_many(
            _chain_leads(nc.owner_node, actor, action.assignee),
            kind=NotificationKind.CAPA_READY_TO_VERIFY,
            title=f"اقدام «{action.title}» انجام شد و منتظر تایید شماست",
            body=f"{nc.code}: {nc.title}", url=f"/quality/{nc.pk}",
        )


def _require_verifier(nc: NonConformance, action: CorrectiveAction, actor) -> None:
    """Manager, and not the assignee: whoever did the work cannot be the one who confirms it worked —
    not even the مدیر عامل. If the only manager is the assignee, another manager must verify."""
    require_manager(actor, nc.owner_node)
    _require_in_progress(nc)
    if action.status != ActionStatus.DONE:
        raise ConflictError(
            f"این اقدام «{action.get_status_display()}» است و فقط اقدام «انجام شده» تایید می‌شود.",
            code="wrong_status", status=action.status,
        )
    if action.assignee_id == actor.pk:
        raise ConflictError(
            "کسی که اقدام را انجام داده نمی‌تواند آن را تایید کند؛ مسئول دیگری باید تایید کند.",
            code="self_verification",
        )


@transaction.atomic
def verify_action(nc: NonConformance, action: CorrectiveAction, *, actor, note="") -> CorrectiveAction:
    nc = _lock(nc.pk)
    action = _lock_action(nc, action.pk)
    _require_verifier(nc, action, actor)
    action.status, action.verified_by, action.verified_at = ActionStatus.VERIFIED, actor, timezone.now()
    action.verification_note = _clean_text(note, "note", max_length=TEXT_MAX, required=False)
    action.save(update_fields=["status", "verified_by", "verified_at", "verification_note", "updated_at"])
    record_event(
        QualityEventKind.ACTION_VERIFIED, actor, nc=nc, action=action, subject_title=action.title,
        from_status=ActionStatus.DONE, to_status=ActionStatus.VERIFIED, note=action.verification_note,
    )
    _tell(action.assignee, actor, NotificationKind.CAPA_VERIFIED, nc, f"اقدام «{action.title}» تایید شد", f"{nc.code}: {nc.title}")
    return action


@transaction.atomic
def fail_verification(nc: NonConformance, action: CorrectiveAction, *, actor, reason) -> CorrectiveAction:
    """The check found it did not actually work: back to the assignee (IN_PROGRESS), reason required."""
    nc = _lock(nc.pk)
    action = _lock_action(nc, action.pk)
    _require_verifier(nc, action, actor)
    reason = _clean_text(reason, "reason", max_length=TEXT_MAX)
    action.status, action.completed_at = ActionStatus.IN_PROGRESS, None
    action.save(update_fields=["status", "completed_at", "updated_at"])
    record_event(
        QualityEventKind.ACTION_VERIFICATION_FAILED, actor, nc=nc, action=action, subject_title=action.title,
        from_status=ActionStatus.DONE, to_status=ActionStatus.IN_PROGRESS, note=reason,
    )
    _tell(action.assignee, actor, NotificationKind.CAPA_VERIFICATION_FAILED, nc, f"تایید اقدام «{action.title}» ناموفق بود", reason)
    return action


@transaction.atomic
def cancel_action(nc: NonConformance, action: CorrectiveAction, *, actor, reason) -> CorrectiveAction:
    """The way out of an action that is no longer needed. It stays on the record, and no longer counts
    towards closing."""
    nc = _lock(nc.pk)
    action = _lock_action(nc, action.pk)
    require_manager(actor, nc.owner_node)
    _require_in_progress(nc)
    _require_not_final(action)
    previous = action.status
    action.cancel_reason = _clean_text(reason, "reason", max_length=TEXT_MAX)
    action.status, action.completed_at = ActionStatus.CANCELLED, None
    action.save(update_fields=["status", "cancel_reason", "completed_at", "updated_at"])
    record_event(
        QualityEventKind.ACTION_CANCELLED, actor, nc=nc, action=action, subject_title=action.title,
        from_status=previous, to_status=ActionStatus.CANCELLED, note=action.cancel_reason,
    )
    _tell(action.assignee, actor, NotificationKind.CAPA_CANCELLED, nc, f"اقدام «{action.title}» لغو شد", action.cancel_reason)
    return action
