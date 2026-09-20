"""Input validation and output shaping for the designer's document body.

The body is one ordered list of blocks. Each block has a `type` (the V_1.0
`dynamic_items` discriminator) and a payload whose shape depends on it, so the
input serializer dispatches on `type` rather than declaring one big union.
"""
from django.urls import reverse
from rest_framework import serializers

from apps.core.constants import (
    RESPONSIBILITY_ROLE_ORDER,
    ResponsibilityRole,
    SectionType,
)

from .serializers import DocumentDetailSerializer

MAX_SECTIONS = 100

_FIELD_LABELS = {
    "lines": "خطوط",
    "heading": "عنوان",
    "body": "متن",
    "extra_boxes": "کادرهای متن",
    "file_ids": "فایل‌ها",
    "roles": "نقش‌ها",
    "notes": "توضیحات",
    "post": "سمت",
    "supervisor": "ناظر",
    "text": "متن",
    "rows": "ردیف‌ها",
    "items": "ضمیمه‌ها",
    "caption": "عنوان ضمیمه",
    "document_id": "مستند ضمیمه",
}


def _text(*, max_length: int, required=False, **kwargs) -> serializers.CharField:
    # Free text is stored exactly as typed: no trimming, so the user's own
    # line breaks and spacing survive a save/load round trip.
    return serializers.CharField(
        allow_blank=True,
        trim_whitespace=False,
        max_length=max_length,
        required=required,
        default="" if not required else serializers.empty,
        **kwargs,
    )


# --------------------------------------------------------------------------
# One serializer per block type
# --------------------------------------------------------------------------


class _SectionInput(serializers.Serializer):
    id = serializers.IntegerField(required=False, allow_null=True)


class ShortExplanationInput(_SectionInput):
    lines = serializers.ListField(child=_text(max_length=2000), max_length=200, default=list)


class LongExplanationInput(_SectionInput):
    heading = _text(max_length=500)
    body = _text(max_length=100_000)
    extra_boxes = serializers.ListField(child=_text(max_length=100_000), max_length=50, default=list)
    file_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=200, default=list)

    def validate_file_ids(self, value):
        # A file can hang off a block once; keep first occurrence, keep order.
        return list(dict.fromkeys(value))


class _RoleRowInput(serializers.Serializer):
    role = serializers.ChoiceField(choices=ResponsibilityRole.choices)
    post = _text(max_length=255)
    supervisor = _text(max_length=255)
    text = _text(max_length=5000)


class ResponsibilitiesInput(_SectionInput):
    roles = serializers.ListField(child=_RoleRowInput(), min_length=4, max_length=4)
    notes = serializers.ListField(child=_text(max_length=5000), max_length=50, default=list)

    def validate_roles(self, value):
        if sorted(r["role"] for r in value) != sorted(ResponsibilityRole.values):
            raise serializers.ValidationError("هر چهار ردیف مسئولیت باید دقیقاً یک‌بار ارسال شود.")
        return value


class _ChangeRowInput(serializers.Serializer):
    id = serializers.IntegerField(required=False, allow_null=True)
    text = serializers.CharField(
        max_length=5000, error_messages={"blank": "عنوان تغییر را وارد کنید.", "required": "عنوان تغییر را وارد کنید."}
    )


class ChangesTableInput(_SectionInput):
    rows = serializers.ListField(child=_ChangeRowInput(), max_length=500, default=list)


class _AttachmentItemInput(serializers.Serializer):
    caption = serializers.CharField(
        max_length=255, error_messages={"blank": "عنوان ضمیمه را بنویسید.", "required": "عنوان ضمیمه را بنویسید."}
    )
    document_id = serializers.IntegerField(
        min_value=1, error_messages={"required": "مستند ضمیمه را انتخاب کنید.", "null": "مستند ضمیمه را انتخاب کنید."}
    )


class AttachmentInput(_SectionInput):
    items = serializers.ListField(child=_AttachmentItemInput(), max_length=200, default=list)


SECTION_INPUTS = {
    SectionType.SHORT_EXPLANATION: ShortExplanationInput,
    SectionType.LONG_EXPLANATION: LongExplanationInput,
    SectionType.RESPONSIBILITIES: ResponsibilitiesInput,
    SectionType.CHANGES_TABLE: ChangesTableInput,
    SectionType.ATTACHMENT: AttachmentInput,
}

#: A document has one Responsibilities table (it feeds the register columns) and
#: one Changes Table (its rows are joined across revisions). V_1.0 let you add
#: several of either, but then updated the register from whichever it saved last.
SINGLETON_SECTIONS = (SectionType.RESPONSIBILITIES, SectionType.CHANGES_TABLE)


def _flatten(detail, path=()):
    """Yield (path, message) for every leaf of a nested DRF error structure."""
    if isinstance(detail, dict):
        for key, value in detail.items():
            yield from _flatten(value, path + (str(key),))
    elif isinstance(detail, (list, tuple)):
        for index, value in enumerate(detail):
            yield from _flatten(value, path + (str(index),) if isinstance(value, (dict, list)) else path)
    else:
        yield path, str(detail)


def _describe(path) -> str:
    for part in reversed(path):
        if part in _FIELD_LABELS:
            return _FIELD_LABELS[part]
    return ""


class ContentInputSerializer(serializers.Serializer):
    """The body of a `PUT /documents/{id}/content/` request."""

    base_version = serializers.IntegerField(min_value=0)
    footnote1 = serializers.CharField(allow_blank=True, max_length=255, required=False, default="")
    footnote2 = serializers.CharField(allow_blank=True, max_length=255, required=False, default="")
    sections = serializers.ListField(
        child=serializers.DictField(), allow_empty=True, max_length=MAX_SECTIONS
    )

    def validate_sections(self, raw_sections):
        validated, messages = [], []

        for index, raw in enumerate(raw_sections):
            number = index + 1
            section_type = raw.get("type")
            serializer_class = SECTION_INPUTS.get(section_type)
            if serializer_class is None:
                messages.append(f"بخش {number}: نوع بخش نامعتبر است.")
                continue

            serializer = serializer_class(data=raw)
            if not serializer.is_valid():
                title = SectionType(section_type).label
                for path, message in _flatten(serializer.errors):
                    label = _describe(path)
                    where = f"بخش {number} ({title})" + (f" — {label}" if label else "")
                    messages.append(f"{where}: {message}")
                continue

            validated.append({"type": section_type, **serializer.validated_data})

        if messages:
            raise serializers.ValidationError(messages)

        for singleton in SINGLETON_SECTIONS:
            if sum(1 for s in validated if s["type"] == singleton) > 1:
                raise serializers.ValidationError(
                    [f"در هر مستند فقط یک بخش «{SectionType(singleton).label}» مجاز است."]
                )

        ids = [s["id"] for s in validated if s.get("id")]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError(["شناسه بخش‌ها تکراری است."])
        return validated


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------


def file_payload(document, record, request) -> dict:
    url = reverse("document-download-file", kwargs={"pk": document.pk, "file_id": record.pk})
    return {
        "id": record.pk,
        "name": record.original_name,
        "kind": record.kind,
        "kind_label": record.get_kind_display(),
        "size": record.size,
        "download_url": request.build_absolute_uri(url),
    }


def _section_payload(document, section, request) -> dict:
    base = {"id": section.id, "type": section.type}
    kind = section.type
    content = section.content or {}

    if kind == SectionType.SHORT_EXPLANATION:
        return {**base, "lines": content.get("lines", [])}

    if kind == SectionType.LONG_EXPLANATION:
        return {
            **base,
            "heading": content.get("heading", ""),
            "body": content.get("body", ""),
            "extra_boxes": content.get("extra_boxes", []),
            "files": [file_payload(document, f, request) for f in section.files.all()],
        }

    if kind == SectionType.RESPONSIBILITIES:
        rows = list(section.responsibility_rows.all())
        by_role = {r.role: r for r in rows if r.role}
        roles = []
        for role in RESPONSIBILITY_ROLE_ORDER:
            row = by_role.get(role)
            roles.append(
                {
                    "role": role,
                    "role_label": ResponsibilityRole(role).label,
                    "post": row.post if row else "",
                    "supervisor": row.supervisor if row else "",
                    "text": row.text if row else "",
                }
            )
        return {**base, "roles": roles, "notes": [r.text for r in rows if not r.role]}

    if kind == SectionType.CHANGES_TABLE:
        return {
            **base,
            "rows": [{"id": r.id, "text": r.text, "date": r.date} for r in section.change_rows.all()],
        }

    if kind == SectionType.ATTACHMENT:
        return {
            **base,
            "items": [
                {
                    "caption": item.caption,
                    "document": {
                        "id": item.target_id,
                        "full_code": item.target.full_code,
                        "title": item.target.title,
                        "status": item.target.status,
                        "status_label": item.target.get_status_display(),
                    },
                }
                for item in section.attachment_items.all()
            ],
        }

    return base


def content_payload(document, request) -> dict:
    """Everything the designer needs to render one document."""
    sections = document.sections.prefetch_related(
        "files", "responsibility_rows", "change_rows", "attachment_items__target"
    )
    logo_url = None
    if document.logo:
        # The stored name is unique per upload, so it doubles as a cache-buster.
        version = document.logo.name.rsplit("/", 1)[-1]
        logo_url = (
            request.build_absolute_uri(reverse("document-logo", kwargs={"pk": document.pk}))
            + f"?v={version}"
        )

    return {
        "document": DocumentDetailSerializer(document, context={"request": request}).data,
        "version": document.content_version,
        "editable": document.is_editable,
        "logo_url": logo_url,
        "footnote1": document.footnote1,
        "footnote2": document.footnote2,
        "sections": [_section_payload(document, s, request) for s in sections],
        "previous_changes": [
            {
                "id": row.id,
                "document_id": row.section.document_id,
                "revision": row.section.document.revision,
                "revision_display": row.section.document.revision_display,
                "text": row.text,
                "date": row.date,
            }
            for row in document.previous_change_rows()
        ],
    }
