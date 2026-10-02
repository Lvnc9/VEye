from django.utils import timezone
from rest_framework import serializers

from apps.documents.models import Document
from apps.organization.access import access_for
from apps.organization.models import OrgNode

from .access import can_manage
from .models import NcSeverity, NcSource, NcStatus, NonConformance, QualityEvent


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
    can_edit = serializers.SerializerMethodField()
    can_triage = serializers.SerializerMethodField()
    can_reopen = serializers.SerializerMethodField()

    class Meta:
        model = NonConformance
        fields = [
            "id", "code", "title", "description", "source", "source_label", "severity", "severity_label",
            "status", "status_label", "owner_node", "owner_node_name", "reported_by", "reported_by_name",
            "detected_on", "related_document", "related_document_code", "related_document_title",
            "root_cause", "rejection_reason", "effectiveness_note", "accepted_at", "closed_at",
            "created_at", "can_edit", "can_triage", "can_reopen",
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
        return obj.status == NcStatus.REJECTED and self._manager(obj)


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
    def _label(value: str) -> str:
        try:
            return NcStatus(value).label if value else ""
        except ValueError:
            return ""

    def get_from_status_label(self, obj) -> str:
        return self._label(obj.from_status)

    def get_to_status_label(self, obj) -> str:
        return self._label(obj.to_status)
