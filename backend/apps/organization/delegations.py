"""Temporary cover for a مسئول (Phase 16) — the one place that writes a `Delegation`.

A delegation needs no locking dance: unlike `Membership` there is no "exactly one primary"
invariant to keep, and two overlapping delegations to the same person are harmless (they simply
both say "covers this node today"). What this module owns is the validation the serializer cannot
see, and telling the delegate (Phase 15's notifications) in the same transaction.
"""
from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import ConflictError
from apps.core.text import normalize_title
from apps.notifications import services as notifications
from apps.notifications.models import NotificationKind

from .models import Delegation


@transaction.atomic
def create_delegation(*, node, delegate, starts_on, ends_on, note="", created_by=None) -> Delegation:
    if not node.is_active:
        raise ConflictError(
            "برای گرهٔ بایگانی‌شده نمی‌توان جانشین تعیین کرد.", code="node_archived", node_id=node.pk
        )
    if not delegate.is_active or delegate.is_developer:
        raise ConflictError("این شخص نمی‌تواند جانشین شود.", code="delegate_not_eligible", user_id=delegate.pk)
    if ends_on < timezone.localdate():
        raise ConflictError("بازهٔ جانشینی نباید کاملاً در گذشته باشد.", code="window_in_past")
    delegation = Delegation.objects.create(
        node=node,
        delegate=delegate,
        starts_on=starts_on,
        ends_on=ends_on,
        note=normalize_title(note),
        created_by=created_by,
    )
    notifications.notify(
        delegate,
        kind=NotificationKind.DELEGATION_RECEIVED,
        title=f"جانشین «{node.name}» شدید ({starts_on} تا {ends_on})",
        body=delegation.note,
        url="/organization",
    )
    return delegation


@transaction.atomic
def end_delegation(delegation: Delegation) -> None:
    """Revoke early (or tidy a finished one). A delegation that has simply expired needs nothing —
    this exists for «برگشتم» and for correcting a mistake."""
    delegation.delete()
