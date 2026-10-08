from django.utils import timezone
from rest_framework import serializers

from apps.organization.access import access_for
from apps.organization.models import OrgNode

from .access import can_manage
from .models import Announcement


class AnnouncementSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.full_name", read_only=True)
    author_title = serializers.CharField(source="author.title", read_only=True)
    audience_name = serializers.SerializerMethodField()
    is_withdrawn = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = [
            "id", "title", "body", "author", "author_name", "author_title", "audience_node", "audience_name",
            "pinned", "expires_on", "created_at", "edited_at", "withdrawn_at", "is_withdrawn", "is_expired",
            "can_manage",
        ]
        read_only_fields = fields

    def get_audience_name(self, obj) -> str:
        return obj.audience_node.name if obj.audience_node_id else "همهٔ سازمان"

    def get_is_withdrawn(self, obj) -> bool:
        return obj.withdrawn_at is not None

    def get_is_expired(self, obj) -> bool:
        return obj.expires_on is not None and obj.expires_on < timezone.localdate()

    def get_can_manage(self, obj) -> bool:
        return obj.withdrawn_at is None and can_manage(access_for(self.context["request"]), obj)


class AnnouncementCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    body = serializers.CharField(max_length=10000)
    audience_node = serializers.PrimaryKeyRelatedField(queryset=OrgNode.objects.all(), required=False, allow_null=True, default=None)
    pinned = serializers.BooleanField(required=False, default=False)
    expires_on = serializers.DateField(required=False, allow_null=True, default=None)


class AnnouncementUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False)
    body = serializers.CharField(max_length=10000, required=False)
    pinned = serializers.BooleanField(required=False)
    expires_on = serializers.DateField(required=False, allow_null=True)
