"""Where every Notification is created — the only place that writes one, so the dedupe rule and
the kind vocabulary cannot drift between callers.

Callers already hold the transaction for the thing being reported (`workflow.submit`,
`memberships.add_membership`, …) and call these functions directly, inside it — never from a
signal. A scheduled caller (`tasks.py`) is not inside anyone else's transaction, so a failed
dedupe there costs nothing beyond the one row.
"""
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Notification


def notify(recipient, *, kind, title, body="", url="", dedupe_key="") -> Notification | None:
    """One notification for one person. With `dedupe_key` set, a second call for the same
    (recipient, dedupe_key) pair is a no-op — the row already says what needs saying — which is
    what lets a periodic reminder task run as often as it likes without spamming. Returns
    `None` when the call was a no-op, the created row otherwise.
    """
    if not dedupe_key:
        return Notification.objects.create(recipient=recipient, kind=kind, title=title, body=body, url=url)
    try:
        with transaction.atomic():
            return Notification.objects.create(
                recipient=recipient, kind=kind, title=title, body=body, url=url, dedupe_key=dedupe_key
            )
    except IntegrityError:
        return None


def notify_many(recipients, **kwargs) -> list[Notification]:
    """`notify` for several people at once (e.g. every مسئول eligible to confirm one document) —
    de-duplicated by user id first, so someone who leads two ancestor nodes is told once, not
    once per node."""
    seen: set[int] = set()
    created = []
    for recipient in recipients:
        if recipient.pk in seen:
            continue
        seen.add(recipient.pk)
        result = notify(recipient, **kwargs)
        if result is not None:
            created.append(result)
    return created


def unread_count(user) -> int:
    """The number the کارتابل badge folds in (`apps.dashboard.views.DashboardInboxView`)."""
    return Notification.objects.filter(recipient=user, read_at__isnull=True).count()


def mark_read(notification: Notification) -> None:
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at", "updated_at"])


def mark_all_read(user) -> int:
    """Returns how many rows were touched (0 is a perfectly normal answer, not an error)."""
    return Notification.objects.filter(recipient=user, read_at__isnull=True).update(
        read_at=timezone.now(), updated_at=timezone.now()
    )
