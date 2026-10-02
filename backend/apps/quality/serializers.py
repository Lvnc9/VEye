from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from apps.documents.models import Document
from apps.organization.access import access_for
from apps.organization.models import OrgNode

from .access import can_manage
from .models import (
    FINAL_ACTION_STATUSES,
    OPEN_ACTION_STATUSES,
    ActionStatus,
    CorrectiveAction,
    NcSeverity,
    NcSource,
    NcStatus,
    NonConformance,
    QualityEvent,
    QualityEventKind,
)

User = get_user_model()


class NonConformanceSerializer(serializers.ModelSerializer):
    """A record as the list and the detail page need it. The `can_*` flags come from the same
    functions the write endpoints enforce (`access.can_manage`, the reporter's OPEN window), so a
    button is never offered that the server would refuse. Needs `request` in the context; build the
    queryset with `select_related("owner_node", "reported_by", "related_document")`."""

    code = serializers.CharField(read_only=True)
    source_label = serializers.CharField(source="get_source_display", read_only=True)
    severity_label = serializers.CharField(source="get_severity_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    owner_node_name = serializers.CharField(source="owner_node.name", read_only=True)
    reported_by_name = serializers.CharField(source="reported_by.full_name", read_only=True)
    related_document_code = serializers.SerializerMethodField()
    related_document_title = serializers.SerializerMethodField()
    #: Derived, never stored (queries.with_action_counts) — absent only if a caller forgot to annotate.
    actions_total = serializers.IntegerField(read_only=True, default=0)
    actions_verified = serializers.IntegerField(read_only=True, default=0)
    actions_overdue = serializers.IntegerField(read_only=True, default=0)
    can_edit = serializers.SerializerMethodField()
    can_triage = serializers.SerializerMethodField()
    can_reopen = serializers.SerializerMethodField()
    can_add_action = serializers.SerializerMethodField()
    can_close = serializers.SerializerMethodField()

    class Meta:
        model = NonConformance
        fields = [
            "id", "code", "title", "description", "source", "source_label", "severity", "severity_label",
            "status", "status_label", "owner_node", "owner_node_name", "reported_by", "reported_by_name",
            "detected_on", "related_document", "related_document_code", "related_document_title",
            "root_cause", "rejection_reason", "effectiveness_note", "accepted_at", "closed_at",
            "created_at", "actions_total", "actions_verified", "actions_overdue",
            "can_edit", "can_triage", "can_reopen", "can_add_action", "can_close",
        ]
        read_only_fields = fields

    def _manager(self, obj) -> bool:
        return can_manage(access_for(self.context["request"]), obj.owner_node)

    def get_related_document_code(self, obj):
        return obj.related_document.full_code if obj.related_document_id else None

    def get_related_document_title(self, obj):
        return obj.related_document.title if obj.related_document_id else None

    def get_can_edit(self, obj) -> bool:
        if obj.status == NcStatus.IN_PROGRESS:
            return self._manager(obj)
        if obj.status == NcStatus.OPEN:
            return self._manager(obj) or obj.reported_by_id == self.context["request"].user.pk
        return False

    def get_can_triage(self, obj) -> bool:
        return obj.status == NcStatus.OPEN and self._manager(obj)

    def get_can_reopen(self, obj) -> bool:
        return obj.status in (NcStatus.REJECTED, NcStatus.CLOSED) and self._manager(obj)

    def get_can_add_action(self, obj) -> bool:
        return obj.status == NcStatus.IN_PROGRESS and self._manager(obj)

    def get_can_close(self, obj) -> bool:
        """Everything the *button* can know: a manager, in progress, ≥ 1 action and all of them
        verified. (The effectiveness note is typed in the dialog; the server still re-checks the lot.)"""
        total = getattr(obj, "actions_total", 0)
        return (
            obj.status == NcStatus.IN_PROGRESS
            and total > 0
            and getattr(obj, "actions_verified", 0) == total
            and self._manager(obj)
        )


class NonConformanceCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(max_length=4000)
    owner_node = serializers.PrimaryKeyRelatedField(queryset=OrgNode.objects.all())
    source = serializers.ChoiceField(choices=NcSource.choices, required=False, default=NcSource.INTERNAL)
    severity = serializers.ChoiceField(choices=NcSeverity.choices, required=False, default=NcSeverity.MINOR)
    detected_on = serializers.DateField(required=False, default=None, allow_null=True)
    related_document = serializers.PrimaryKeyRelatedField(
        queryset=Document.objects.all(), required=False, allow_null=True, default=None
    )


class NonConformanceUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(max_length=4000, required=False)
    owner_node = serializers.PrimaryKeyRelatedField(queryset=OrgNode.objects.all(), required=False)
    source = serializers.ChoiceField(choices=NcSource.choices, required=False)
    severity = serializers.ChoiceField(choices=NcSeverity.choices, required=False)
    detected_on = serializers.DateField(required=False)
    related_document = serializers.PrimaryKeyRelatedField(
        queryset=Document.objects.all(), required=False, allow_null=True
    )


class AcceptSerializer(serializers.Serializer):
    root_cause = serializers.CharField(max_length=4000)
    severity = serializers.ChoiceField(choices=NcSeverity.choices, required=False, allow_null=True, default=None)


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=4000)


class QualityEventSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    nc_code = serializers.SerializerMethodField()
    nc_title = serializers.SerializerMethodField()
    from_status_label = serializers.SerializerMethodField()
    to_status_label = serializers.SerializerMethodField()

    class Meta:
        model = QualityEvent
        fields = [
            "id", "kind", "kind_label", "nc", "nc_code", "nc_title", "actor_name", "actor_title",
            "subject_title", "from_status", "to_status", "from_status_label", "to_status_label",
            "note", "created_at",
        ]
        read_only_fields = fields

    def get_nc_code(self, obj):
        return obj.nc.code if obj.nc_id else None

    def get_nc_title(self, obj):
        return obj.nc.title if obj.nc_id else None

    @staticmethod
    def _label(kind: str, value: str) -> str:
        """A status's Persian label — from the record's enum or the action's, by the kind of event.
        `action_due_changed` carries ISO dates in these fields, `action_assigned` carries none."""
        if not value:
            return ""
        enum = ActionStatus if kind in _ACTION_STATUS_KINDS else NcStatus if kind.startswith("nc_") else None
        try:
            return enum(value).label if enum else ""
        except ValueError:
            return ""

    def get_from_status_label(self, obj) -> str:
        return self._label(obj.kind, obj.from_status)

    def get_to_status_label(self, obj) -> str:
        return self._label(obj.kind, obj.to_status)


_ACTION_STATUS_KINDS = {
    QualityEventKind.ACTION_STATUS_CHANGED,
    QualityEventKind.ACTION_VERIFIED,
    QualityEventKind.ACTION_VERIFICATION_FAILED,
    QualityEventKind.ACTION_CANCELLED,
}


class CorrectiveActionSerializer(serializers.ModelSerializer):
    """An action as the detail page's panel needs it. The flags are computed by the same functions the
    endpoints enforce; the context carries `request`, the `nc` (its status and node decide what may
    change) and `manager` (whether the viewer manages that record — computed once, not per row)."""

    status_label = serializers.CharField(source="get_status_display", read_only=True)
    assignee_name = serializers.CharField(source="assignee.full_name", read_only=True)
    assignee_title = serializers.CharField(source="assignee.title", read_only=True)
    assignee_is_active = serializers.BooleanField(source="assignee.is_active", read_only=True)
    verified_by_name = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_set_status = serializers.SerializerMethodField()
    can_verify = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()

    class Meta:
        model = CorrectiveAction
        fields = [
            "id", "nc", "title", "description", "assignee", "assignee_name", "assignee_title",
            "assignee_is_active", "due_on", "status", "status_label", "is_overdue", "completed_at",
            "verified_by_name", "verified_at", "verification_note", "cancel_reason", "created_at",
            "can_edit", "can_set_status", "can_verify", "can_cancel",
        ]
        read_only_fields = fields

    def _live(self, obj) -> bool:
        return self.context["nc"].status == NcStatus.IN_PROGRESS and obj.status not in FINAL_ACTION_STATUSES

    def get_verified_by_name(self, obj):
        return obj.verified_by.full_name if obj.verified_by_id else None

    def get_is_overdue(self, obj) -> bool:
        return obj.status in OPEN_ACTION_STATUSES and obj.due_on < timezone.localdate()

    def get_can_edit(self, obj) -> bool:
        return self._live(obj) and self.context["manager"]

    def get_can_set_status(self, obj) -> bool:
        mine = obj.assignee_id == self.context["request"].user.pk
        return self._live(obj) and (self.context["manager"] or mine)

    def get_can_verify(self, obj) -> bool:
        return (
            self._live(obj)
            and obj.status == ActionStatus.DONE
            and self.context["manager"]
            and obj.assignee_id != self.context["request"].user.pk
        )

    def get_can_cancel(self, obj) -> bool:
        return self._live(obj) and self.context["manager"]


class ActionCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(max_length=4000, required=False, allow_blank=True, default="")
    assignee = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    due_on = serializers.DateField()


class ActionUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(max_length=4000, required=False, allow_blank=True)
    assignee = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False)
    due_on = serializers.DateField(required=False)
    status = serializers.ChoiceField(
        choices=[ActionStatus.TODO, ActionStatus.IN_PROGRESS, ActionStatus.DONE], required=False
    )


class VerifySerializer(serializers.Serializer):
    note = serializers.CharField(max_length=4000, required=False, allow_blank=True, default="")


class CloseSerializer(serializers.Serializer):
    effectiveness_note = serializers.CharField(max_length=4000)
