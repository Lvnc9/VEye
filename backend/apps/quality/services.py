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
from apps.core.text import normalize_title, to_persian_digits
from apps.documents.authority import approve_eligible_users
from apps.notifications import services as notifications
from apps.notifications.models import NotificationKind
from apps.organization.access import OrgAccess, users_leading_at_or_above
from apps.organization.models import OrgNode
from apps.organization.tree import lock_node

from .access import (
    NOT_A_MANAGER,
    can_manage,
    can_report,
    require_audit_planner,
    require_audit_runner,
    require_manager,
)
from .models import (
    FINAL_ACTION_STATUSES,
    ActionStatus,
    AuditStatus,
    CorrectiveAction,
    RISK_SCALE,
    InternalAudit,
    NcSeverity,
    NcSource,
    NcStatus,
    NonConformance,
    QualityEvent,
    QualityEventKind,
    RiskItem,
    RiskStatus,
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


def _require_active_node(node: OrgNode, message: str = "برای گرهٔ بایگانی‌شده نمی‌توان عدم‌انطباق ثبت کرد.") -> None:
    if not node.is_active:
        raise ConflictError(message, code="node_archived", node_id=node.pk)


def _chain_leads(node: OrgNode, *skip):
    """The مسئولان of `node` and every node above it; with nobody leading, the مدیر عامل (the same
    fallback a document with no owner node has). `skip` are people not to tell — whoever just acted,
    and for a verification, the person who did the work."""
    people = list(users_leading_at_or_above(node)) or list(approve_eligible_users())
    excluded = {person.pk for person in skip if person is not None}
    return [person for person in people if person.pk not in excluded]


# -- report and edit ---------------------------------------------------------


def _file(
    *, actor, title, description, owner_node, source, severity, detected_on, related_document, audit=None
) -> NonConformance:
    """Validate and create the row — the part a report and an audit's finding have in common. It
    writes no history and tells nobody: each caller's event differs (a finding's one line is
    `finding_raised`), so each records its own."""
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
    return NonConformance.objects.create(
        title=title, description=description, source=source, severity=severity, owner_node=node,
        reported_by=actor, detected_on=detected_on, related_document=related_document, audit=audit,
    )


def _announce(nc: NonConformance, actor, body: str = "") -> None:
    """Tell the people who lead the record's node (and above) that it exists."""
    notifications.notify_many(
        _chain_leads(nc.owner_node, actor),
        kind=NotificationKind.NC_REPORTED,
        title=f"«{nc.code}» ثبت شد: {nc.title}",
        body=body or nc.owner_node.name,
        url=f"/quality/{nc.pk}",
    )


@transaction.atomic
def report(
    *, actor, title, description, owner_node, source=NcSource.INTERNAL, severity=NcSeverity.MINOR,
    detected_on=None, related_document=None,
) -> NonConformance:
    """Anyone may report one. It needs an *active* node — whose process this is — but no authority
    over it: a person who sees a problem in another unit is exactly who should be able to say so."""
    nc = _file(
        actor=actor, title=title, description=description, owner_node=owner_node, source=source,
        severity=severity, detected_on=detected_on, related_document=related_document,
    )
    record_event(
        QualityEventKind.NC_REPORTED, actor, nc=nc, subject_title=nc.title, to_status=NcStatus.OPEN
    )
    _announce(nc, actor)
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


def _require_eligible(user, who: str = "مسئول اقدام", code: str = "assignee_not_eligible") -> None:
    if not user.is_active or user.is_developer:
        raise ConflictError(f"این شخص نمی‌تواند {who} شود.", code=code, user_id=user.pk)


def _require_future(due_on: datetime.date) -> None:
    if due_on < timezone.localdate():
        raise ConflictError("مهلت نمی‌تواند در گذشته باشد.", code="due_in_past")


def _tell(person, actor, kind, record, title: str, body: str = "") -> None:
    """Notify one person about a record — never the person who just acted. `record` is a
    non-conformance, an audit or a risk; the link goes to its own page."""
    if person.pk != actor.pk:
        if isinstance(record, InternalAudit):
            url = f"/quality/audits/{record.pk}"
        elif isinstance(record, RiskItem):
            url = f"/quality/risks/{record.pk}"
        else:
            url = f"/quality/{record.pk}"
        notifications.notify(person, kind=kind, title=title, body=body, url=url)


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


# -- internal audits -----------------------------------------------------------

AUDIT_EDITABLE = {
    "title": "عنوان",
    "scope_node": "گرهٔ ممیزی‌شونده",
    "planned_on": "تاریخ برنامه",
    "lead_auditor": "ممیز اصلی",
}
#: Once an audit is running its scope and plan are fixed — findings already hang off them — but the
#: person leading it can still be replaced (an auditor falls ill mid-audit).
AUDIT_EDITABLE_WHILE_RUNNING = {"lead_auditor"}


def _lock_audit(pk: int) -> InternalAudit:
    try:
        return (
            InternalAudit.objects.select_for_update(of=("self",))
            .select_related("scope_node", "lead_auditor")
            .get(pk=pk)
        )
    except InternalAudit.DoesNotExist:
        raise NotFound("ممیزی یافت نشد.")


def _require_audit_status(audit: InternalAudit, expected, verb: str) -> None:
    allowed = (expected,) if isinstance(expected, str) else tuple(expected)
    if audit.status not in allowed:
        raise ConflictError(
            f"این ممیزی در وضعیت «{audit.get_status_display()}» است و نمی‌توان آن را {verb}.",
            code="wrong_status",
            status=audit.status,
        )


def _require_plan_date(planned_on: datetime.date) -> None:
    if planned_on < timezone.localdate():
        raise ConflictError("تاریخ برنامهٔ ممیزی نمی‌تواند در گذشته باشد.", code="planned_in_past")


def _tell_auditor(audit: InternalAudit, actor) -> None:
    _tell(
        audit.lead_auditor, actor, NotificationKind.AUDIT_PLANNED, audit, f"ممیزی «{audit.code}» به شما سپرده شد",
        f"{audit.title} — {audit.scope_node.name}",
    )


@transaction.atomic
def plan_audit(*, actor, title, scope_node, lead_auditor, planned_on) -> InternalAudit:
    """Only `manage_quality` plans one. The auditor must be someone who can act (active, not the
    developer account); whether they are *independent* of the audited unit is not enforced — the
    quality manager who names them is trusted with that judgement."""
    require_audit_planner(actor)
    title = normalize_title(_clean_text(title, "title", max_length=TITLE_MAX))
    _require_eligible(lead_auditor, "ممیز اصلی", "auditor_not_eligible")
    _require_plan_date(planned_on)
    node = lock_node(scope_node.pk)
    _require_active_node(node, "برای گرهٔ بایگانی‌شده نمی‌توان ممیزی برنامه‌ریزی کرد.")
    audit = InternalAudit.objects.create(
        title=title, scope_node=node, lead_auditor=lead_auditor, planned_on=planned_on
    )
    record_event(
        QualityEventKind.AUDIT_PLANNED, actor, audit=audit, subject_title=audit.title,
        to_status=AuditStatus.PLANNED, note=lead_auditor.full_name,
    )
    _tell_auditor(audit, actor)
    notifications.notify_many(
        _chain_leads(node, actor, lead_auditor),
        kind=NotificationKind.AUDIT_PLANNED,
        title=f"ممیزی داخلی «{node.name}» برنامه‌ریزی شد",
        body=audit.title,
        url=f"/quality/audits/{audit.pk}",
    )
    return audit


@transaction.atomic
def edit_audit(audit: InternalAudit, *, actor, changes: dict) -> InternalAudit:
    """`manage_quality` only. While it is PLANNED everything may change; once it is running only the
    lead auditor can be replaced; a finished or called-off audit is read-only. Only real changes are
    recorded, and a changed auditor is told."""
    audit = _lock_audit(audit.pk)
    require_audit_planner(actor)
    _require_audit_status(audit, (AuditStatus.PLANNED, AuditStatus.IN_PROGRESS), "ویرایش کرد")
    allowed = AUDIT_EDITABLE if audit.status == AuditStatus.PLANNED else AUDIT_EDITABLE_WHILE_RUNNING
    blocked = set(changes) - set(allowed)
    if blocked:
        raise ValidationError({name: ["این فیلد پس از آغاز ممیزی قابل ویرایش نیست."] for name in sorted(blocked)})

    edited, old_auditor = [], None
    if "title" in changes:
        title = normalize_title(_clean_text(changes["title"], "title", max_length=TITLE_MAX))
        if title != audit.title:
            audit.title = title
            edited.append("title")
    if "planned_on" in changes and changes["planned_on"] != audit.planned_on:
        _require_plan_date(changes["planned_on"])
        audit.planned_on = changes["planned_on"]
        edited.append("planned_on")
    if "scope_node" in changes and changes["scope_node"].pk != audit.scope_node_id:
        node = lock_node(changes["scope_node"].pk)
        _require_active_node(node, "برای گرهٔ بایگانی‌شده نمی‌توان ممیزی برنامه‌ریزی کرد.")
        audit.scope_node = node
        edited.append("scope_node")
    auditor_changed = "lead_auditor" in changes and changes["lead_auditor"].pk != audit.lead_auditor_id
    if auditor_changed:
        _require_eligible(changes["lead_auditor"], "ممیز اصلی", "auditor_not_eligible")
        old_auditor = audit.lead_auditor.full_name
        audit.lead_auditor = changes["lead_auditor"]
        edited.append("lead_auditor")
    if not edited:
        return audit
    audit.save(update_fields=[*edited, "updated_at"])
    plain = [name for name in edited if name != "lead_auditor"]
    if plain:
        record_event(
            QualityEventKind.AUDIT_EDITED, actor, audit=audit, subject_title=audit.title,
            note="، ".join(AUDIT_EDITABLE[name] for name in plain),
        )
    if auditor_changed:
        record_event(
            QualityEventKind.AUDIT_AUDITOR_CHANGED, actor, audit=audit, subject_title=audit.title,
            note=f"{old_auditor} ← {audit.lead_auditor.full_name}",
        )
        _tell_auditor(audit, actor)
    return audit


@transaction.atomic
def start_audit(audit: InternalAudit, *, actor) -> InternalAudit:
    """PLANNED → IN_PROGRESS, by the lead auditor or `manage_quality`. Starting early (before
    `planned_on`) is allowed: the date is a plan, not a gate."""
    audit = _lock_audit(audit.pk)
    require_audit_runner(actor, audit)
    _require_audit_status(audit, AuditStatus.PLANNED, "آغاز کرد")
    audit.status, audit.started_at = AuditStatus.IN_PROGRESS, timezone.now()
    audit.save(update_fields=["status", "started_at", "updated_at"])
    record_event(
        QualityEventKind.AUDIT_STARTED, actor, audit=audit, subject_title=audit.title,
        from_status=AuditStatus.PLANNED, to_status=AuditStatus.IN_PROGRESS,
    )
    return audit


@transaction.atomic
def complete_audit(audit: InternalAudit, *, actor, summary) -> InternalAudit:
    """IN_PROGRESS → COMPLETED with a written summary. «No findings» is a legitimate result — but it has
    to be said, so the summary is required whether or not anything was raised."""
    audit = _lock_audit(audit.pk)
    require_audit_runner(actor, audit)
    _require_audit_status(audit, AuditStatus.IN_PROGRESS, "تکمیل کرد")
    audit.summary = _clean_text(summary, "summary", max_length=TEXT_MAX)
    audit.status, audit.completed_at = AuditStatus.COMPLETED, timezone.now()
    audit.save(update_fields=["summary", "status", "completed_at", "updated_at"])
    record_event(
        QualityEventKind.AUDIT_COMPLETED, actor, audit=audit, subject_title=audit.title,
        from_status=AuditStatus.IN_PROGRESS, to_status=AuditStatus.COMPLETED, note=audit.summary,
    )
    return audit


@transaction.atomic
def cancel_audit(audit: InternalAudit, *, actor, reason) -> InternalAudit:
    """Called off before it is finished — `manage_quality` only, reason required. Findings already
    raised stay: they are real non-conformances and carry on their own course."""
    audit = _lock_audit(audit.pk)
    require_audit_planner(actor)
    _require_audit_status(audit, (AuditStatus.PLANNED, AuditStatus.IN_PROGRESS), "لغو کرد")
    previous = audit.status
    audit.cancel_reason = _clean_text(reason, "reason", max_length=TEXT_MAX)
    audit.status = AuditStatus.CANCELLED
    audit.save(update_fields=["cancel_reason", "status", "updated_at"])
    record_event(
        QualityEventKind.AUDIT_CANCELLED, actor, audit=audit, subject_title=audit.title,
        from_status=previous, to_status=AuditStatus.CANCELLED, note=audit.cancel_reason,
    )
    _tell(
        audit.lead_auditor, actor, NotificationKind.AUDIT_CANCELLED, audit, f"ممیزی «{audit.code}» لغو شد",
        audit.cancel_reason,
    )
    return audit


@transaction.atomic
def raise_finding(
    audit: InternalAudit, *, actor, title, description, owner_node=None, severity=NcSeverity.MINOR,
    detected_on=None, related_document=None,
) -> NonConformance:
    """A finding is a non-conformance, filed from inside a running audit: its source is AUDIT, it
    points back at the audit, and its owner node is the audited node — or any node *beneath* it (an
    audit of a unit that finds the problem in one of its sections). Observations are simply MINOR.
    Only the lead auditor (or `manage_quality`) raises one, and only while the audit is IN_PROGRESS."""
    audit = _lock_audit(audit.pk)
    require_audit_runner(actor, audit)
    if audit.status != AuditStatus.IN_PROGRESS:
        raise ConflictError(
            "یافته فقط وقتی ممیزی «در حال انجام» است ثبت می‌شود.", code="audit_not_in_progress", status=audit.status
        )
    node = lock_node(owner_node.pk) if owner_node is not None else audit.scope_node
    if not node.path.startswith(audit.scope_node.path):
        raise ValidationError(
            {"owner_node": ["گرهٔ یافته باید خودِ گرهٔ ممیزی‌شونده یا یکی از زیرمجموعه‌های آن باشد."]}
        )
    nc = _file(
        actor=actor, title=title, description=description, owner_node=node, source=NcSource.AUDIT,
        severity=severity, detected_on=detected_on, related_document=related_document, audit=audit,
    )
    # One line for the moment, on the audit's timeline *and* the record's: no separate `nc_reported`.
    record_event(
        QualityEventKind.FINDING_RAISED, actor, nc=nc, audit=audit, subject_title=nc.title,
        to_status=NcStatus.OPEN, note=f"{audit.code}: {audit.title}",
    )
    _announce(nc, actor, body=f"یافتهٔ {audit.code} · {nc.owner_node.name}")
    return nc


# -- risks ---------------------------------------------------------------------

RISK_EDITABLE = {
    "title": "عنوان",
    "description": "شرح",
    "owner_node": "گرهٔ مربوط",
    "owner": "مسئول ریسک",
    "mitigation_plan": "برنامهٔ کاهش",
    "review_on": "تاریخ بازنگری",
}


def _lock_risk(pk: int) -> RiskItem:
    try:
        return (
            RiskItem.objects.select_for_update(of=("self",))
            .select_related("owner_node", "owner", "created_by")
            .get(pk=pk)
        )
    except RiskItem.DoesNotExist:
        raise NotFound("ریسک یافت نشد.")


def _scale(value, field: str) -> int:
    """1-5, checked here as well as in the serializer and the database: the rule must hold whoever calls."""
    if isinstance(value, bool) or not isinstance(value, int) or value not in RISK_SCALE:
        raise ValidationError({field: ["مقدار باید عددی از ۱ تا ۵ باشد."]})
    return value


def _assessment(likelihood: int, impact: int) -> str:
    """«۳×۴» — how an assessment reads in the history."""
    return to_persian_digits(f"{likelihood}×{impact}")


def _require_review_date(review_on: datetime.date) -> None:
    if review_on < timezone.localdate():
        raise ConflictError("تاریخ بازنگری نمی‌تواند در گذشته باشد.", code="review_in_past")


def _tell_owner(risk: RiskItem, actor) -> None:
    if risk.owner is not None:
        _tell(risk.owner, actor, NotificationKind.RISK_ASSIGNED, risk, f"ریسک «{risk.code}» به شما سپرده شد", risk.title)


@transaction.atomic
def create_risk(
    *, actor, title, description, owner_node, likelihood, impact, owner=None, mitigation_plan="", review_on=None
) -> RiskItem:
    """`manage_quality`, or a lead of the node (or one above it): unlike a non-conformance, nobody
    «reports» a risk — it is a judgement about a process, made by whoever answers for it. It needs an
    active node, a likelihood and an impact (1-5) and a description; an owner, a plan and a review date
    are optional (an owner, if named, must be able to act)."""
    node = lock_node(owner_node.pk)
    require_manager(actor, node)
    _require_active_node(node, "برای گرهٔ بایگانی‌شده نمی‌توان ریسک ثبت کرد.")
    title = normalize_title(_clean_text(title, "title", max_length=TITLE_MAX))
    description = _clean_text(description, "description", max_length=TEXT_MAX)
    mitigation_plan = _clean_text(mitigation_plan, "mitigation_plan", max_length=TEXT_MAX, required=False)
    likelihood, impact = _scale(likelihood, "likelihood"), _scale(impact, "impact")
    if owner is not None:
        _require_eligible(owner, "مسئول ریسک", "owner_not_eligible")
    if review_on is not None:
        _require_review_date(review_on)
    risk = RiskItem.objects.create(
        title=title, description=description, owner_node=node, owner=owner, created_by=actor,
        likelihood=likelihood, impact=impact, mitigation_plan=mitigation_plan, review_on=review_on,
    )
    record_event(
        QualityEventKind.RISK_CREATED, actor, risk=risk, subject_title=risk.title,
        to_status=RiskStatus.IDENTIFIED, note=_assessment(likelihood, impact),
    )
    _tell_owner(risk, actor)
    return risk


@transaction.atomic
def edit_risk(risk: RiskItem, *, actor, changes: dict) -> RiskItem:
    """Everything about a risk can change, at any status — a risk is a living judgement, so this is
    permissive like a project's status: every change is *recorded*, none is guarded. Three kinds of line
    are written, only for what really changed: `risk_edited` (the plain fields, named), `risk_assessed`
    («۳×۴ ← ۴×۴») and `risk_status_changed` (from → to). Moving it to another node needs authority there
    too; a newly named owner is told."""
    risk = _lock_risk(risk.pk)
    require_manager(actor, risk.owner_node)

    edited = []
    if "title" in changes:
        title = normalize_title(_clean_text(changes["title"], "title", max_length=TITLE_MAX))
        if title != risk.title:
            risk.title = title
            edited.append("title")
    if "description" in changes:
        description = _clean_text(changes["description"], "description", max_length=TEXT_MAX)
        if description != risk.description:
            risk.description = description
            edited.append("description")
    if "mitigation_plan" in changes:
        plan = _clean_text(changes["mitigation_plan"], "mitigation_plan", max_length=TEXT_MAX, required=False)
        if plan != risk.mitigation_plan:
            risk.mitigation_plan = plan
            edited.append("mitigation_plan")
    if "review_on" in changes and changes["review_on"] != risk.review_on:
        if changes["review_on"] is not None:
            _require_review_date(changes["review_on"])
        risk.review_on = changes["review_on"]
        edited.append("review_on")
    if "owner_node" in changes and changes["owner_node"].pk != risk.owner_node_id:
        node = lock_node(changes["owner_node"].pk)
        _require_active_node(node, "برای گرهٔ بایگانی‌شده نمی‌توان ریسک ثبت کرد.")
        if not can_manage(OrgAccess(actor), node):
            raise PermissionDenied("برای انتقال باید مسئول گرهٔ مقصد (یا گره‌های بالادست آن) هم باشید.")
        risk.owner_node = node
        edited.append("owner_node")
    new_owner = None
    if "owner" in changes and (changes["owner"].pk if changes["owner"] else None) != risk.owner_id:
        new_owner = changes["owner"]
        if new_owner is not None:
            _require_eligible(new_owner, "مسئول ریسک", "owner_not_eligible")
        risk.owner = new_owner
        edited.append("owner")

    before = (risk.likelihood, risk.impact)
    if "likelihood" in changes:
        risk.likelihood = _scale(changes["likelihood"], "likelihood")
    if "impact" in changes:
        risk.impact = _scale(changes["impact"], "impact")
    assessed = (risk.likelihood, risk.impact) != before

    previous_status = risk.status
    if "status" in changes and changes["status"] != risk.status:
        if changes["status"] not in RiskStatus.values:
            raise ValidationError({"status": ["وضعیت نامعتبر است."]})
        risk.status = changes["status"]

    moved = risk.status != previous_status
    if not (edited or assessed or moved):
        return risk
    fields = [*edited, *(["likelihood", "impact"] if assessed else []), *(["status"] if moved else [])]
    risk.save(update_fields=[*fields, "updated_at"])
    if edited:
        record_event(
            QualityEventKind.RISK_EDITED, actor, risk=risk, subject_title=risk.title,
            note="، ".join(RISK_EDITABLE[name] for name in edited),
        )
    if assessed:
        record_event(
            QualityEventKind.RISK_ASSESSED, actor, risk=risk, subject_title=risk.title,
            note=f"{_assessment(*before)} ← {_assessment(risk.likelihood, risk.impact)}",
        )
    if moved:
        record_event(
            QualityEventKind.RISK_STATUS_CHANGED, actor, risk=risk, subject_title=risk.title,
            from_status=previous_status, to_status=risk.status,
        )
    if "owner" in edited:
        _tell_owner(risk, actor)
    return risk


def risk_review_recipients(risk: RiskItem):
    """Whom a review reminder goes to: the named owner, or — with nobody named, or the owner since
    deactivated — the leads of the risk's node chain (the مدیر عامل if nobody leads)."""
    if risk.owner is not None and risk.owner.is_active:
        return [risk.owner]
    return _chain_leads(risk.owner_node)
