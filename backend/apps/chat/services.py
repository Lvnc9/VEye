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
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.core.exceptions import ConflictError

from .models import (
    DIRECT_CONVERSATION_CONSTRAINT,
    NODE_CONVERSATION_CONSTRAINT,
    PARTICIPANT_CONSTRAINT,
    Conversation,
    ConversationKind,
    ConversationParticipant,
    Message,
    MessageKind,
)

KEY_WIDTH = 10
MESSAGE_MAX_LENGTH = 4000


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


# --------------------------------------------------------------------------
# Messages
# --------------------------------------------------------------------------


def _lock_conversation(pk: int) -> Conversation:
    try:
        return Conversation.objects.select_for_update(of=("self",)).select_related("node").get(pk=pk)
    except Conversation.DoesNotExist:
        raise NotFound("گفتگو یافت نشد.")


def require_can_post(conversation: Conversation, actor) -> None:
    """An archived node's channel is read-only (owner's decision); so is a DM whose other person
    has been deactivated. `ConversationSerializer.can_post` shows the same answer."""
    if conversation.kind == ConversationKind.NODE:
        if not conversation.node.is_active:
            raise ConflictError(
                "این گره بایگانی شده و گفتگوی آن فقط‌خواندنی است.", code="conversation_read_only"
            )
        return
    other = conversation.participants.exclude(user=actor).select_related("user").first()
    if other is None or not other.user.is_active:
        raise ConflictError("این شخص غیرفعال است و نمی‌توان برای او پیام فرستاد.", code="user_inactive")


def _clean_body(body: str) -> str:
    body = (body or "").strip()
    if not body:
        raise ValidationError({"body": ["متن پیام نمی‌تواند خالی باشد."]})
    if len(body) > MESSAGE_MAX_LENGTH:
        raise ValidationError({"body": [f"متن پیام حداکثر {MESSAGE_MAX_LENGTH} نویسه است."]})
    return body


def _append(conversation: Conversation, message: Message) -> None:
    """Under the conversation's row lock, so `last_message_*` always names the newest message."""
    conversation.last_message_at = message.created_at
    conversation.last_message_id = message.pk
    conversation.save(update_fields=["last_message_at", "last_message_id", "updated_at"])


@transaction.atomic
def send_message(conversation: Conversation, *, sender, body: str) -> Message:
    """Post a message. The caller has already decided the sender may read the conversation. The
    sender's own read mark moves to their message, so it never counts as unread for them."""
    body = _clean_body(body)
    conversation = _lock_conversation(conversation.pk)
    require_can_post(conversation, sender)
    message = Message.objects.create(
        conversation=conversation,
        sender=sender,
        sender_name=sender.full_name,
        sender_title=sender.title,
        body=body,
    )
    _append(conversation, message)
    ensure_participant(conversation, sender)
    ConversationParticipant.objects.filter(conversation=conversation, user=sender).update(
        last_read_message_id=message.pk
    )
    return message


@transaction.atomic
def post_system_message(node, body: str) -> Message:
    """A system line in a node's channel («… به گفتگو اضافه شد»), so a group stays legible as
    membership changes. Written in the caller's transaction; no sender."""
    conversation = _lock_conversation(node_conversation(node).pk)
    message = Message.objects.create(
        conversation=conversation, kind=MessageKind.SYSTEM, sender=None, sender_name="", body=body
    )
    _append(conversation, message)
    return message


def mark_read(conversation: Conversation, *, user, up_to: int) -> int | None:
    """Move the person's read mark forward to `up_to` (never back, never past the newest message).
    One conditional UPDATE, so two tabs racing can only ever move it forward."""
    participant = ensure_participant(conversation, user)
    newest = Conversation.objects.filter(pk=conversation.pk).values_list("last_message_id", flat=True).first()
    target = min(up_to, newest or 0)
    if target > 0:
        ConversationParticipant.objects.filter(pk=participant.pk).filter(
            Q(last_read_message_id__isnull=True) | Q(last_read_message_id__lt=target)
        ).update(last_read_message_id=target)
    return ConversationParticipant.objects.filter(pk=participant.pk).values_list(
        "last_read_message_id", flat=True
    ).first()


@transaction.atomic
def delete_message(message: Message, *, actor) -> Message:
    """Tombstone a message. **Only its sender, no exception** — not a lead, not the مدیر عامل
    (owner's decision). Idempotent. No editing exists."""
    try:
        message = Message.objects.select_for_update().get(pk=message.pk)
    except Message.DoesNotExist:
        raise NotFound("پیام یافت نشد.")
    if message.sender_id is None or message.sender_id != actor.pk:
        raise PermissionDenied("فقط فرستندهٔ پیام می‌تواند آن را حذف کند.")
    if message.deleted_at is not None:
        return message
    conversation = Conversation.objects.select_related("node").get(pk=message.conversation_id)
    if conversation.kind == ConversationKind.NODE and not conversation.node.is_active:
        raise ConflictError("این گره بایگانی شده و گفتگوی آن فقط‌خواندنی است.", code="conversation_read_only")
    message.deleted_at = timezone.now()
    message.deleted_by = actor
    message.save(update_fields=["deleted_at", "deleted_by", "updated_at"])
    return message
