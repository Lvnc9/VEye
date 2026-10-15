"""Distributing an approved revision to the people who must read it (Phase 21).

`apps.documents` may not read the org chart (a structural test guards it), so the audience is resolved here
and `documents.workflow.approve` hands the document over."""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.core.constants import DocumentStatus, SignOffRole
from apps.core.exceptions import ConflictError

from .models import ReadAcknowledgment


def audience_nodes(document) -> list:
    """The owner node and the active units named in the Responsibilities block."""
    from apps.documents.models import ResponsibilityRow
    from apps.organization.models import OrgNode

    ids = set(
        ResponsibilityRow.objects.filter(section__document=document, unit__isnull=False).values_list("unit_id", flat=True)
    )
    if document.owner_node_id:
        ids.add(document.owner_node_id)
    return list(OrgNode.objects.filter(pk__in=ids, is_active=True))


def audience(document) -> dict:
    """{user: node name} for everyone placed in the audience nodes or beneath them — active people only,
    never the developer account. A person placed twice is listed under their primary placement if it is
    one of them, else the first by path."""
    from apps.organization.access import members_of_subtrees

    return members_of_subtrees(audience_nodes(document))


@transaction.atomic
def distribute(document) -> int:
    """Ask the audience to read `document` (just approved). The three signers have read it already and are
    recorded as such. Idempotent: people already asked are left alone. Returns how many were asked."""
    from apps.notifications import services as notifications
    from apps.notifications.models import NotificationKind

    people = audience(document)
    existing = set(ReadAcknowledgment.objects.filter(document=document).values_list("user_id", flat=True))
    signers = set(
        document.signoffs.filter(role__in=SignOffRole.values, signed_by__isnull=False).values_list("signed_by_id", flat=True)
    )
    now = timezone.now()
    rows = [
        ReadAcknowledgment(
            document=document,
            user=user,
            node_name=node_name,
            acknowledged_at=now if user.pk in signers else None,
        )
        for user, node_name in people.items()
        if user.pk not in existing
    ]
    ReadAcknowledgment.objects.bulk_create(rows)
    notifications.notify_many(
        [row.user for row in rows if row.acknowledged_at is None],
        kind=NotificationKind.DOCUMENT_TO_READ,
        title=f"مستند «{document.full_code}» برای مطالعهٔ شما ابلاغ شد",
        body=document.title,
        url=f"/documents/{document.pk}/edit",
        dedupe_key=f"document:{document.pk}:to-read",
    )
    return len(rows)


@transaction.atomic
def acknowledge(*, user, document_id: int) -> ReadAcknowledgment:
    row = (
        ReadAcknowledgment.objects.select_for_update()
        .select_related("document")
        .filter(document_id=document_id, user=user)
        .first()
    )
    if row is None:
        raise NotFound("این مستند برای مطالعهٔ شما ابلاغ نشده است.")
    if row.document.status != DocumentStatus.UNDER_CONTROL:
        raise ConflictError(
            "این بازنگری دیگر معتبر نیست؛ بازنگری جاری را مطالعه کنید.", code="not_in_force", status=row.document.status
        )
    if row.acknowledged_at is None:
        row.acknowledged_at = timezone.now()
        row.save(update_fields=["acknowledged_at"])
    return row


def pending_for(user):
    """What `user` still has to read: rows not acknowledged, of revisions still in force."""
    return (
        ReadAcknowledgment.objects.filter(
            user=user, acknowledged_at__isnull=True, document__status=DocumentStatus.UNDER_CONTROL
        )
        .select_related("document")
        .order_by("-created_at", "-id")
    )
