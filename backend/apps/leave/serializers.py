from django.utils import timezone
from rest_framework import serializers

from apps.organization.access import access_for

from .access import can_decide
from .models import Holiday, LeaveRequest, LeaveStatus, LeaveType
from .workdays import HolidayCache


class LeaveRequestSerializer(serializers.ModelSerializer):
    """A request as the list needs it. `days` is derived; `can_decide` / `can_cancel` come from the same
    rules the endpoints enforce, so a button is never offered that the server would refuse."""

    leave_type_label = serializers.CharField(source="get_leave_type_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    requester_name = serializers.CharField(source="requester.full_name", read_only=True)
    requester_title = serializers.CharField(source="requester.title", read_only=True)
    days = serializers.SerializerMethodField()
    calendar_days = serializers.IntegerField(read_only=True)
    can_decide = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()

    class Meta:
        model = LeaveRequest
        fields = [
            "id", "requester", "requester_name", "requester_title", "node", "node_name", "leave_type",
            "leave_type_label", "starts_on", "ends_on", "days", "calendar_days", "reason", "status", "status_label",
            "decided_by_name", "decided_at", "decision_note", "cancelled_at", "created_at",
            "can_decide", "can_cancel",
        ]
        read_only_fields = fields

    def get_days(self, obj) -> int:
        """Working days (Phase 22); the holidays are read once per response, not once per row."""
        cache = self.context.setdefault("holidays", HolidayCache())
        return cache.working_days(obj.starts_on, obj.ends_on)

    def get_can_decide(self, obj) -> bool:
        return obj.status == LeaveStatus.PENDING and can_decide(access_for(self.context["request"]), obj)

    def get_can_cancel(self, obj) -> bool:
        if obj.requester_id != self.context["request"].user.pk:
            return False
        if obj.status == LeaveStatus.PENDING:
            return True
        return obj.status == LeaveStatus.APPROVED and obj.starts_on > timezone.localdate()


class LeaveCreateSerializer(serializers.Serializer):
    leave_type = serializers.ChoiceField(choices=LeaveType.choices, default=LeaveType.ANNUAL)
    starts_on = serializers.DateField()
    ends_on = serializers.DateField()
    reason = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


class NoteSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = ["id", "date", "title"]
        # The view answers a duplicate date with a Persian 409; DRF's own unique check would say 400 in English.
        extra_kwargs = {"date": {"validators": []}}

    def validate_title(self, value):
        from apps.core.text import normalize_title

        title = normalize_title(value)
        if not title:
            raise serializers.ValidationError("عنوان تعطیلی را بنویسید.")
        return title


class SpanSerializer(serializers.Serializer):
    starts_on = serializers.DateField()
    ends_on = serializers.DateField()

    def validate(self, attrs):
        if attrs["ends_on"] < attrs["starts_on"]:
            raise serializers.ValidationError({"ends_on": ["تاریخ پایان نمی‌تواند پیش از تاریخ شروع باشد."]})
        if (attrs["ends_on"] - attrs["starts_on"]).days > 366:
            raise serializers.ValidationError({"ends_on": ["بازه نباید بیش از یک سال باشد."]})
        return attrs
