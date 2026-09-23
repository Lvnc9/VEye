"""Chat rules — the one place that writes Conversation and ConversationParticipant.

Node conversations are created **eagerly**, one per node, in the same transaction as the node
(`tree._insert` calls `create_node_conversation`), including the company root — so "does this
node have a channel?" is never a question a query has to ask. `node_conversation()` is the
idempotent safety net for nodes that predate this app (there is no data migration, by policy).

DMs are de-duplicated by `direct_key` under a partial unique index: a racing loser gets the
IntegrityError, re-reads and returns the winner's row — the `get_or_create`-under-a-constraint
idiom `documents/services.py` and `pdfgen/services.py` already use.
"""
from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from apps.core.exceptions import ConflictError

from .models import (
    DIRECT_CONVERSATION_CONSTRAINT,
    NODE_CONVERSATION_CONSTRAINT,
    PARTICIPANT_CONSTRAINT,
    Conversation,
    ConversationKind,
    ConversationParticipant,
    MessageKind,
)

KEY_WIDTH = 10


def direct_key(a_id: int, b_id: int) -> str:
    """The canonical key of the DM between two people — the same whichever of them opens it."""
    low, high = sorted((a_id, b_id))
    return f"{low:0{KEY_WIDTH}d}:{high:0{KEY_WIDTH}d}"


def _constraint_name(exc: IntegrityError) -> str | None:
    return getattr(getattr(exc.__cause__, "diag", None), "constraint_name", None)


# --------------------------------------------------------------------------
# Node conversations
# --------------------------------------------------------------------------


def create_node_conversation(node) -> Conversation:
    """Called by the tree service inside the node's own transaction."""
    return Conversation.objects.create(kind=ConversationKind.NODE, node=node, created_by=node.created_by)


def node_conversation(node) -> Conversation:
    """The node's channel, creating it if the node predates chat. Safe under a race."""
    existing = Conversation.objects.filter(kind=ConversationKind.NODE, node=node).first()
    if existing is not None:
        return existing
    try:
        with transaction.atomic():
            return Conversation.objects.create(kind=ConversationKind.NODE, node=node)
    except IntegrityError as exc:
        if _constraint_name(exc) != NODE_CONVERSATION_CONSTRAINT:
            raise
        return Conversation.objects.get(kind=ConversationKind.NODE, node=node)


def node_message_count(node) -> int:
    """Human messages in the node's channel — what stops the node being deleted. System lines
    («… اضافه شد») are bookkeeping, not anyone's words, so they do not block."""
    return sum(
        conversation.messages.filter(kind=MessageKind.TEXT).count()
        for conversation in node.conversations.all()
    )


def delete_node_conversations(node) -> None:
    """Remove the (message-less) channel of a node that is being deleted. The caller has already
    checked `node_message_count(node) == 0`."""
    Conversation.objects.filter(node=node).delete()


# --------------------------------------------------------------------------
# Participants
# --------------------------------------------------------------------------


def ensure_participant(conversation: Conversation, user) -> ConversationParticipant:
    """The person's participant row, created lazily (for a NODE conversation it only holds the
    read mark). Safe under a race: two tabs opening the same channel get one row."""
    existing = ConversationParticipant.objects.filter(conversation=conversation, user=user).first()
    if existing is not None:
        return existing
    try:
        with transaction.atomic():
            return ConversationParticipant.objects.create(conversation=conversation, user=user)
    except IntegrityError as exc:
        if _constraint_name(exc) != PARTICIPANT_CONSTRAINT:
            raise
        return ConversationParticipant.objects.get(conversation=conversation, user=user)


def open_node_conversation(*, actor, node) -> Conversation:
    """Open a node's channel for someone already allowed to read it (the view checks)."""
    conversation = node_conversation(node)
    ensure_participant(conversation, actor)
    return conversation


# --------------------------------------------------------------------------
# Direct conversations
# --------------------------------------------------------------------------


def open_direct(*, actor, other) -> tuple[Conversation, bool]:
    """The DM between `actor` and `other`, and whether it was created by this call.

    Any active person may message any other (docs/11 §5.3): the owner's flow is "click a person on
    the chart and chat", and a chart showing people you cannot message is worse than no chart.
    """
    if other.pk == actor.pk:
        raise ValidationError({"user": ["گفتگو با خودتان ممکن نیست."]})
    if not other.is_active:
        raise ConflictError("این شخص غیرفعال است و نمی‌توان با او گفتگو کرد.", code="user_inactive")

    key = direct_key(actor.pk, other.pk)
    existing = Conversation.objects.filter(kind=ConversationKind.DIRECT, direct_key=key).first()
    if existing is not None:
        return existing, False
    try:
        with transaction.atomic():
            conversation = Conversation.objects.create(kind=ConversationKind.DIRECT, direct_key=key, created_by=actor)
            ConversationParticipant.objects.bulk_create(
                [
                    ConversationParticipant(conversation=conversation, user=actor),
                    ConversationParticipant(conversation=conversation, user=other),
                ]
            )
    except IntegrityError as exc:
        if _constraint_name(exc) != DIRECT_CONVERSATION_CONSTRAINT:
            raise
        return Conversation.objects.get(kind=ConversationKind.DIRECT, direct_key=key), False
    return conversation, True
