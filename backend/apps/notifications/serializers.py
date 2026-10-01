from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ["id", "kind", "kind_label", "title", "body", "url", "created_at", "read_at", "is_read"]
        read_only_fields = fields

    def get_is_read(self, obj) -> bool:
        return obj.read_at is not None
