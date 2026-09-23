from rest_framework import serializers

from apps.organization.models import OrgNodeKind

from .models import Conversation, ConversationKind


class OpenDirectSerializer(serializers.Serializer):
    user = serializers.IntegerField()


class OpenNodeSerializer(serializers.Serializer):
    node = serializers.IntegerField()


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
