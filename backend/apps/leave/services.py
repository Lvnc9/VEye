"""Every write to leave goes through here (Phase 19): lock the row, check who may, check the status,
write, tell the people who need to know — in one transaction, so two deciders acting at once cannot both
win, and a refused change tells nobody."""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.core.exceptions import ConflictError
from apps.core.text import to_persian_digits
from apps.notifications import services as notifications
from apps.notifications.models import NotificationKind
from apps.organization.access import OrgAccess

from .access import NOT_A_DECIDER, can_decide, deciders
from .models import HOLDING_STATUSES, LeaveRequest, LeaveStatus, LeaveType

TEXT_MAX = 2000


def _clean(value, field: str, *, required: bool) -> str:
    text = (value or "").strip()
    if required and not text:
        raise ValidationError({field: ["این فیلد الزامی است."]})
    if len(text) > TEXT_MAX:
        raise ValidationError({field: [f"نباید بیش از {to_persian_digits(str(TEXT_MAX))} نویسه باشد."]})
    return text


def _home_node(user):
    """Where the requester sits: their primary membership, else any membership, else nowhere (then only
    the مدیر عامل can decide)."""
    membership = user.memberships.select_related("node").order_by("-is_primary", "id").first()
    return membership.node if membership else None


def _lock(pk: int) -> LeaveRequest:
    try:
        return LeaveRequest.objects.select_for_update(of=("self",)).select_related("requester", "node").get(pk=pk)
    except LeaveRequest.DoesNotExist:
        raise NotFound("درخواست مرخصی یافت نشد.")


def _require_status(leave: LeaveRequest, allowed, verb: str) -> None:
    if leave.status not in allowed:
        raise ConflictError(
            f"این درخواست «{leave.get_status_display()}» است و نمی‌توان آن را {verb}.",
            code="wrong_status",
            status=leave.status,
        )


def _span(leave: LeaveRequest) -> str:
    return f"{leave.get_leave_type_display()}، {to_persian_digits(str(leave.days))} روز"


@transaction.atomic
def request_leave(*, actor, leave_type=LeaveType.ANNUAL, starts_on, ends_on, reason="") -> LeaveRequest:
    if not actor.is_active or actor.is_developer:
        raise PermissionDenied("این حساب نمی‌تواند درخواست مرخصی ثبت کند.")
    if leave_type not in LeaveType.values:
        raise ValidationError({"leave_type": ["نوع مرخصی نامعتبر است."]})
    if ends_on < starts_on:
        raise ValidationError({"ends_on": ["تاریخ پایان نمی‌تواند پیش از تاریخ شروع باشد."]})
    reason = _clean(reason, "reason", required=False)
    # Lock this person's holding requests, so two submissions at once cannot both pass the overlap check.
    clash = (
        LeaveRequest.objects.select_for_update()
        .filter(requester=actor, status__in=HOLDING_STATUSES, starts_on__lte=ends_on, ends_on__gte=starts_on)
        .order_by("starts_on")
        .first()
    )
    if clash is not None:
        raise ConflictError(
            "این بازه با درخواست مرخصی دیگری از شما هم‌پوشانی دارد.", code="leave_overlaps", other=clash.pk
        )
    node = _home_node(actor)
    leave = LeaveRequest.objects.create(
        requester=actor, node=node, node_name=node.name if node else "", leave_type=leave_type,
        starts_on=starts_on, ends_on=ends_on, reason=reason,
    )
    notifications.notify_many(
        deciders(leave),
        kind=NotificationKind.LEAVE_REQUESTED,
        title=f"درخواست مرخصی از {actor.full_name}",
        body=_span(leave),
        url="/leave",
    )
    return leave


def _decide(leave: LeaveRequest, actor, status: str, note: str, kind, title: str) -> LeaveRequest:
    leave = _lock(leave.pk)
    if actor.pk == leave.requester_id:
        raise PermissionDenied("نمی‌توانید دربارهٔ درخواست مرخصی خودتان تصمیم بگیرید.")
    if not can_decide(OrgAccess(actor), leave):
        raise PermissionDenied(NOT_A_DECIDER)
    _require_status(leave, (LeaveStatus.PENDING,), "تصمیم گرفت")
    leave.status, leave.decision_note = status, note
    leave.decided_by, leave.decided_by_name, leave.decided_at = actor, actor.full_name, timezone.now()
    leave.save(update_fields=["status", "decision_note", "decided_by", "decided_by_name", "decided_at", "updated_at"])
    notifications.notify(leave.requester, kind=kind, title=title, body=note or _span(leave), url="/leave")
    return leave


@transaction.atomic
def approve(leave: LeaveRequest, *, actor, note="") -> LeaveRequest:
    return _decide(
        leave, actor, LeaveStatus.APPROVED, _clean(note, "note", required=False),
        NotificationKind.LEAVE_APPROVED, "درخواست مرخصی شما تایید شد",
    )


@transaction.atomic
def reject(leave: LeaveRequest, *, actor, note) -> LeaveRequest:
    """A refusal says why — the requester reads it."""
    return _decide(
        leave, actor, LeaveStatus.REJECTED, _clean(note, "note", required=True),
        NotificationKind.LEAVE_REJECTED, "درخواست مرخصی شما رد شد",
    )


@transaction.atomic
def cancel(leave: LeaveRequest, *, actor) -> LeaveRequest:
    """The requester withdraws it: a pending request any time; an approved one only before its first day
    (once it has begun it is a fact, not a plan). Whoever approved it is told."""
    leave = _lock(leave.pk)
    if actor.pk != leave.requester_id:
        raise PermissionDenied("فقط خودِ درخواست‌دهنده می‌تواند درخواست مرخصی را لغو کند.")
    _require_status(leave, HOLDING_STATUSES, "لغو کرد")
    if leave.status == LeaveStatus.APPROVED and leave.starts_on <= timezone.localdate():
        raise ConflictError("این مرخصی آغاز شده است و دیگر لغو نمی‌شود.", code="leave_started")
    was_approved = leave.status == LeaveStatus.APPROVED
    leave.status, leave.cancelled_at = LeaveStatus.CANCELLED, timezone.now()
    leave.save(update_fields=["status", "cancelled_at", "updated_at"])
    if was_approved and leave.decided_by_id and leave.decided_by_id != actor.pk:
        notifications.notify(
            leave.decided_by, kind=NotificationKind.LEAVE_CANCELLED,
            title=f"{actor.full_name} مرخصی تاییدشده‌اش را لغو کرد", body=_span(leave), url="/leave",
        )
    return leave
