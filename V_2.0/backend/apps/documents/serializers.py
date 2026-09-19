from rest_framework import serializers

from apps.core.constants import DocumentCategory, DocumentGroup, SignOffRole
from apps.core.text import normalize_title

from .models import Document


class DocumentSerializer(serializers.ModelSerializer):
    """A register row. Read-only: documents are created through the dedicated
    create / revise operations, never edited field-by-field over the API."""

    category_label = serializers.CharField(source="get_category_display", read_only=True)
    group_label = serializers.CharField(source="get_group_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    code = serializers.CharField(read_only=True)
    revision_display = serializers.CharField(read_only=True)
    full_code = serializers.CharField(read_only=True)

    action = serializers.CharField(read_only=True)
    can_revise = serializers.SerializerMethodField()
    can_edit = serializers.BooleanField(source="is_editable", read_only=True)
    responsibilities = serializers.SerializerMethodField()
    signoffs = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "category",
            "category_label",
            "title",
            "group",
            "group_label",
            "number",
            "code",
            "revision",
            "revision_display",
            "full_code",
            "status",
            "status_label",
            "action",
            "can_revise",
            "can_edit",
            "responsibilities",
            "signoffs",
            "content_saved_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_can_revise(self, obj: Document) -> bool:
        # The list view annotates has_next_revision to avoid a query per row.
        has_next = getattr(obj, "has_next_revision", None)
        if has_next is None:
            has_next = hasattr(obj, "next_revision")
        return obj.is_finalized and not has_next

    def get_responsibilities(self, obj: Document):
        return obj.responsibility_summary()

    def get_signoffs(self, obj: Document):
        by_role = {s.role: s for s in obj.signoffs.all()}
        result = {}
        for role in SignOffRole.values:
            signoff = by_role.get(role)
            result[role] = (
                {
                    "name": signoff.name,
                    "position": signoff.position,
                    "signed_date": signoff.signed_date,
                }
                if signoff
                else None
            )
        return result


class DocumentCreateSerializer(serializers.Serializer):
    """Input for registering a new document. Mirrors the three fields V_1.0's
    ساخت form required (documents_01.py:678-688), with its "Pleas finish X
    field" warnings as Persian validation messages."""

    category = serializers.ChoiceField(
        choices=DocumentCategory.choices,
        error_messages={
            "required": "دسته بندی را انتخاب کنید.",
            "null": "دسته بندی را انتخاب کنید.",
            "blank": "دسته بندی را انتخاب کنید.",
            # An empty <select> submits "", which DRF reports as invalid_choice, not
            # blank — and from this form that only ever means "nothing chosen".
            "invalid_choice": "دسته بندی را انتخاب کنید.",
        },
    )
    title = serializers.CharField(
        max_length=255,
        error_messages={
            "required": "عنوان را وارد کنید.",
            "null": "عنوان را وارد کنید.",
            "blank": "عنوان را وارد کنید.",
            "max_length": "عنوان نباید بیش از ۲۵۵ نویسه باشد.",
        },
    )
    group = serializers.ChoiceField(
        choices=DocumentGroup.choices,
        error_messages={
            "required": "گروه را انتخاب کنید.",
            "null": "گروه را انتخاب کنید.",
            "blank": "گروه را انتخاب کنید.",
            "invalid_choice": "گروه را انتخاب کنید.",
        },
    )

    def validate_title(self, value: str) -> str:
        value = normalize_title(value)
        if not value:
            raise serializers.ValidationError("عنوان را وارد کنید.")
        return value
