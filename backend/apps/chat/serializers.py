from rest_framework import serializers

from apps.organization.models import OrgNodeKind

from .models import Conversation, ConversationKind, Message, MessageKind
from .services import MESSAGE_MAX_LENGTH

DELETED_TEXT = "پیام حذف شد"
PREVIEW_LENGTH = 120


class OpenDirectSerializer(serializers.Serializer):
    user = serializers.IntegerField()


class OpenNodeSerializer(serializers.Serializer):
    node = serializers.IntegerField()


class SendMessageSerializer(serializers.Serializer):
    # The length rule lives in services._clean_body (Persian message); this only bounds the payload.
    body = serializers.CharField(allow_blank=True, trim_whitespace=False, max_length=MESSAGE_MAX_LENGTH * 2)


class MarkReadSerializer(serializers.Serializer):
    message = serializers.IntegerField(min_value=1)


class MessageSerializer(serializers.ModelSerializer):
    """A deleted message keeps its row (a tombstone) but never its words: `body` is blank and
    `is_deleted` is true; the client shows «پیام حذف شد»."""

    body = serializers.SerializerMethodField()
    is_deleted = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id",
            "conversation",
            "kind",
            "sender",
            "sender_name",
            "sender_title",
            "body",
            "is_deleted",
            "is_mine",
            "can_delete",
            "created_at",
        ]

    def get_body(self, message):
        return "" if message.deleted_at else message.body

    def get_is_deleted(self, message):
        return message.deleted_at is not None

    def get_is_mine(self, message):
        return message.sender_id is not None and message.sender_id == self.context["request"].user.pk

    def get_can_delete(self, message):
        return self.get_is_mine(message) and message.deleted_at is None and message.kind == MessageKind.TEXT


class ConversationSerializer(serializers.ModelSerializer):
    """`counterpart` is the other person of a DM (None for a group channel); `title` is what the
    list shows — the counterpart's name, or the node's. `can_post` is False for an archived node's
    channel (read-only, owner's decision) and for a DM whose counterpart has been deactivated."""

    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    title = serializers.SerializerMethodField()
    counterpart = serializers.SerializerMethodField()
    node_name = serializers.CharField(source="node.name", read_only=True, default=None)
    node_kind = serializers.CharField(source="node.kind", read_only=True, default=None)
    is_company_channel = serializers.SerializerMethodField()
    can_post = serializers.SerializerMethodField()
    unread_count = serializers.IntegerField(read_only=True, default=0)
    my_last_read_message_id = serializers.IntegerField(source="my_last_read", read_only=True, default=None)
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id",
            "kind",
            "kind_label",
            "title",
            "counterpart",
            "node",
            "node_name",
            "node_kind",
            "is_company_channel",
            "can_post",
            "unread_count",
            "my_last_read_message_id",
            "last_message",
            "last_message_at",
            "created_at",
        ]

    def _other(self, conversation):
        if conversation.kind != ConversationKind.DIRECT:
            return None
        me = self.context["request"].user.pk
        # `participants` is prefetched with their users by the view.
        return next((p.user for p in conversation.participants.all() if p.user_id != me), None)

    def get_counterpart(self, conversation):
        other = self._other(conversation)
        if other is None:
            return None
        return {"id": other.pk, "full_name": other.full_name, "title": other.title, "is_active": other.is_active}

    def get_title(self, conversation):
        if conversation.kind == ConversationKind.NODE:
            return conversation.node.name
        other = self._other(conversation)
        return other.full_name if other is not None else "گفتگوی خصوصی"

    def get_is_company_channel(self, conversation):
        return conversation.kind == ConversationKind.NODE and conversation.node.kind == OrgNodeKind.COMPANY

    def get_can_post(self, conversation):
        if conversation.kind == ConversationKind.NODE:
            return conversation.node.is_active
        other = self._other(conversation)
        return other is not None and other.is_active

    def get_last_message(self, conversation):
        """A one-line preview for the list, from annotations (no query per row)."""
        if conversation.last_message_id is None:
            return None
        deleted = getattr(conversation, "last_deleted", None) is not None
        body = "" if deleted else (getattr(conversation, "last_body", "") or "")
        return {
            "id": conversation.last_message_id,
            "kind": getattr(conversation, "last_kind", None),
            "sender_name": getattr(conversation, "last_sender_name", "") or "",
            "preview": body[:PREVIEW_LENGTH],
            "is_deleted": deleted,
        }
