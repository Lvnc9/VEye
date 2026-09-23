"""Per-viewer numbers for a list of conversations — annotated in the one list query, never stored.

Unread = messages after the viewer's read mark that are someone else's words: not their own, not a
system line (bookkeeping, not anyone's message), not deleted. No read mark yet means everything
unread. The same definition feeds the sidebar badge (`unread_total`).
"""
from django.db.models import Count, IntegerField, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from .models import ConversationParticipant, Message, MessageKind


def with_viewer_state(queryset, user):
    my_mark = ConversationParticipant.objects.filter(conversation=OuterRef("pk"), user=user).values(
        "last_read_message_id"
    )[:1]
    queryset = queryset.annotate(my_last_read=Subquery(my_mark, output_field=IntegerField()))
    unread = (
        Message.objects.filter(
            conversation=OuterRef("pk"),
            kind=MessageKind.TEXT,
            deleted_at__isnull=True,
            id__gt=Coalesce(OuterRef("my_last_read"), Value(0)),
        )
        .exclude(sender=user)
        .order_by()
        .values("conversation")
        .annotate(n=Count("id"))
        .values("n")
    )
    last = Message.objects.filter(pk=OuterRef("last_message_id"))
    return queryset.annotate(
        unread_count=Coalesce(Subquery(unread, output_field=IntegerField()), Value(0)),
        last_sender_name=Subquery(last.values("sender_name")[:1]),
        last_kind=Subquery(last.values("kind")[:1]),
        last_body=Subquery(last.values("body")[:1]),
        last_deleted=Subquery(last.values("deleted_at")[:1]),
    )


def unread_total(listed_queryset, user) -> int:
    """The sidebar badge: unread messages across everything the person's «گفتگوها» lists."""
    total = with_viewer_state(listed_queryset, user).aggregate(total=Sum("unread_count"))["total"]
    return total or 0

