from rest_framework import serializers

from apps.core.constants import (
    DocumentCategory,
    DocumentEventKind,
    DocumentGroup,
    DocumentStatus,
    SignOffRole,
)
from apps.core.text import normalize_title

from . import workflow
from .models import Document, DocumentEvent


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
    pdf_status = serializers.SerializerMethodField()
    pdf_built_at = serializers.SerializerMethodField()
    workflow = serializers.SerializerMethodField()

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
            "pdf_status",
            "pdf_built_at",
            "workflow",
            "content_saved_at",
            "created_at",
        ]
        read_only_fields = fields

    def _official_pdf(self, obj: Document):
        # The list view annotates both values (no query per row, and no PDF is
        # ever opened). Elsewhere — create/revise responses, the designer's
        # embedded document — fall back to one lookup.
        if hasattr(obj, "pdf_status_value"):
            return obj.pdf_status_value, obj.pdf_built_at_value
        from apps.pdfgen.models import PdfKind

        build = obj.pdf_builds.filter(kind=PdfKind.OFFICIAL).first()
        return (build.status, build.built_at) if build else (None, None)

    def get_pdf_status(self, obj: Document) -> str:
        """"none" | "building" | "ready" | "failed" — the issued PDF's state."""
        return self._official_pdf(obj)[0] or "none"

    def get_pdf_built_at(self, obj: Document):
        return self._official_pdf(obj)[1]

    def get_workflow(self, obj: Document) -> dict:
        """What the signed-in user can do with this document *now* (Phase 5):
        `step` is what its status awaits (submit / confirm / approve / null),
        `can_act` / `can_return` say whether this user may, and `blocked` is a
        Persian reason when they hold the capability but signed an earlier step
        of the same document. Computed from the prefetched sign-offs — no query
        per row."""
        request = self.context.get("request")
        return workflow.next_step_for(obj, getattr(request, "user", None))

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


class DocumentDetailSerializer(DocumentSerializer):
    """One document (retrieve, and the designer's embedded copy). Adds the note a
    returned author needs; that costs a query, so it is not on the register rows."""

    return_note = serializers.SerializerMethodField()

    class Meta(DocumentSerializer.Meta):
        fields = DocumentSerializer.Meta.fields + ["return_note"]
        read_only_fields = fields

    def get_return_note(self, obj: Document):
        """Why a DRAFT came back (مرجوع) — only while its latest event is that return."""
        if obj.status != DocumentStatus.DRAFT:
            return None
        event = obj.events.order_by("-created_at", "-id").first()
        if event is None or event.kind != DocumentEventKind.RETURNED:
            return None
        return {
            "reason": event.reason,
            "by": event.actor_name,
            "by_title": event.actor_title,
            "at": event.created_at,
        }


class DocumentEventSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    from_status_label = serializers.CharField(source="get_from_status_display", read_only=True)
    to_status_label = serializers.CharField(source="get_to_status_display", read_only=True)

    class Meta:
        model = DocumentEvent
        fields = [
            "id",
            "kind",
            "kind_label",
            "from_status",
            "from_status_label",
            "to_status",
            "to_status_label",
            "actor_name",
            "actor_title",
            "reason",
            "created_at",
        ]
        read_only_fields = fields
