from django.conf import settings
from django.db import models
from django.db.models import CheckConstraint, Index, Q, UniqueConstraint

from apps.core.models import TimeStampedModel
from apps.organization.models import OrgNode

DIRECT_CONVERSATION_CONSTRAINT = "uniq_direct_conversation"
NODE_CONVERSATION_CONSTRAINT = "uniq_node_conversation"
PARTICIPANT_CONSTRAINT = "uniq_conversation_participant"


class ConversationKind(models.TextChoices):
    DIRECT = "DIRECT", "خصوصی"
    NODE = "NODE", "گروهی"


class MessageKind(models.TextChoices):
    TEXT = "TEXT", "پیام"
    SYSTEM = "SYSTEM", "پیام سیستمی"


class Conversation(TimeStampedModel):
    """A 1:1 conversation (DIRECT) or the group channel of one org node (NODE).

    Who may read a NODE conversation is decided from `Membership` at request time (chat/access.py),
    never from a participant row, so it cannot drift when someone changes بخش. A DIRECT
    conversation has no other source of membership: its two participant rows *are* its members.

    A DM's uniqueness lives in its participants, which SQL cannot constrain; `direct_key` —
    "<lower user id>:<higher user id>", zero-padded — moves that invariant into one row's unique
    index, so two people racing to open the same DM get one conversation.
    """

    kind = models.CharField(max_length=8, choices=ConversationKind.choices)
    #: Only for NODE. PROTECT: deleting a node must go through tree.delete_node, which refuses a
    #: node whose channel has messages and removes an empty one itself.
    node = models.ForeignKey(
        OrgNode, null=True, blank=True, on_delete=models.PROTECT, related_name="conversations"
    )
    #: Only for DIRECT; see direct_key() in services.py.
    direct_key = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    #: Denormalised from the newest message, so the کارتابل sorts without a subquery.
    last_message_at = models.DateTimeField(null=True, blank=True)
    last_message_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["direct_key"],
                condition=Q(kind=ConversationKind.DIRECT),
                name=DIRECT_CONVERSATION_CONSTRAINT,
            ),
            UniqueConstraint(
                fields=["node"], condition=Q(kind=ConversationKind.NODE), name=NODE_CONVERSATION_CONSTRAINT
            ),
            CheckConstraint(
                check=(
                    (Q(kind=ConversationKind.DIRECT, node__isnull=True) & ~Q(direct_key=""))
                    | Q(kind=ConversationKind.NODE, node__isnull=False, direct_key="")
                ),
                name="conversation_shape",
            ),
        ]
        indexes = [Index(fields=["-last_message_at"], name="conversation_last_msg_idx")]

    def __str__(self):
        if self.kind == ConversationKind.NODE:
            return f"گفتگوی {self.node.name}"
        return f"گفتگوی خصوصی {self.direct_key}"


class ConversationParticipant(TimeStampedModel):
    """For DIRECT: membership. For NODE: grants nothing — it only holds this person's read mark
    (and, for a lead, puts a channel they opened into their list). Created lazily on first open."""

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversation_participations"
    )
    #: High-water mark: every message with id <= this has been read.
    last_read_message_id = models.BigIntegerField(null=True, blank=True)
    is_muted = models.BooleanField(default=False)

    class Meta:
        constraints = [UniqueConstraint(fields=["conversation", "user"], name=PARTICIPANT_CONSTRAINT)]

    def __str__(self):
        return f"{self.user_id} @ {self.conversation_id}"


class Message(TimeStampedModel):
    """One message. The sender's name and سمت are snapshotted as text (the DocumentEvent device),
    so a thread still reads correctly after the person is renamed or removed.

    Delete is a **tombstone** — the project's first soft delete, and deliberately not a pattern:
    `deleted_at` is set and the serializer shows «پیام حذف شد» instead of the body. Only the sender
    may do it. There is no editing.
    """

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    sender_name = models.CharField(max_length=255)
    sender_title = models.CharField(max_length=255, blank=True)
    kind = models.CharField(max_length=8, choices=MessageKind.choices, default=MessageKind.TEXT)
    body = models.TextField()
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["id"]
        constraints = [
            # A system line («… به گفتگو اضافه شد») has no human sender.
            CheckConstraint(check=Q(kind=MessageKind.TEXT) | Q(sender__isnull=True), name="message_system_has_no_sender"),
            CheckConstraint(
                check=Q(deleted_at__isnull=False) | Q(deleted_by__isnull=True), name="message_deleted_by_needs_deleted_at"
            ),
        ]
        # `?after=<id>` polling and `?before=<id>` paging are both range scans on (conversation, id).
        indexes = [Index(fields=["conversation", "id"], name="message_conversation_id_idx")]

    def __str__(self):
        return f"{self.sender_name}: {self.body[:40]}"
