"""The designer's persistence: saving a document body, uploads, and copying a
body forward into a new revision.

V_1.0 saved a document by walking the widget tree of the Tk window and dumping
it to a JSON file (`SaveSystem.collect_entries_data`, other_folder/utils.py:
487-661), then uploading that file to S3 and patching the Mongo row whose
`json_path` happened to be empty (:691). Here a save is one transaction over
Postgres, keyed by the document's primary key.
"""
from django.core.files import File
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.core.constants import RESPONSIBILITY_ROLE_ORDER, SectionType
from apps.core.exceptions import ConflictError

from .files import inspect_upload, normalize_logo
from .models import (
    AttachmentReference,
    ChangeTableRow,
    Document,
    DocumentFile,
    ResponsibilityRow,
    Section,
)

def _locked(document_id: int) -> Document:
    try:
        return Document.objects.select_for_update().get(pk=document_id)
    except Document.DoesNotExist:
        raise NotFound("مستند یافت نشد.")


def _require_editable(document: Document) -> None:
    if not document.is_editable:
        raise ConflictError(
            "محتوای این مستند پس از ارسال برای تأیید قابل ویرایش نیست.",
            code="content_locked",
        )


def _delete_storage_on_commit(field_file) -> None:
    """Remove a stored file, but only once the surrounding transaction has
    committed — a rollback must not leave a database row pointing at nothing."""
    if field_file and field_file.name:
        name, storage = field_file.name, field_file.storage
        transaction.on_commit(lambda: storage.delete(name))


# --------------------------------------------------------------------------
# Saving a body
# --------------------------------------------------------------------------


def _section_content(item: dict) -> dict:
    kind = item["type"]
    if kind == SectionType.SHORT_EXPLANATION:
        return {"lines": item["lines"]}
    if kind == SectionType.LONG_EXPLANATION:
        return {
            "heading": item["heading"],
            "body": item["body"],
            "extra_boxes": item["extra_boxes"],
        }
    return {}


def _sync_responsibilities(section: Section, item: dict) -> None:
    section.responsibility_rows.all().delete()
    by_role = {row["role"]: row for row in item["roles"]}
    rows = [
        ResponsibilityRow(
            section=section,
            position=position,
            role=role,
            post=by_role[role]["post"],
            supervisor=by_role[role]["supervisor"],
            text=by_role[role]["text"],
        )
        for position, role in enumerate(RESPONSIBILITY_ROLE_ORDER)
    ]
    # Rows past the four roles carry description text only — printed under
    # «توضیحات» (deliver_convert.py:99-114).
    offset = len(rows)
    rows += [
        ResponsibilityRow(section=section, position=offset + i, text=text)
        for i, text in enumerate(item["notes"])
    ]
    ResponsibilityRow.objects.bulk_create(rows)


def _sync_changes(section: Section, item: dict, today) -> None:
    existing = {row.id: row for row in section.change_rows.all()}
    keep = set()
    for position, incoming in enumerate(item["rows"]):
        row = existing.get(incoming.get("id"))
        if row is None:
            # A new line: the date is the server's, never the client's.
            row = ChangeTableRow(section=section, date=today)
        row.position = position
        row.text = incoming["text"]
        row.save()
        keep.add(row.id)
    section.change_rows.exclude(id__in=keep).delete()


def _sync_attachments(section: Section, item: dict) -> None:
    section.attachment_items.all().delete()
    AttachmentReference.objects.bulk_create(
        AttachmentReference(
            section=section,
            position=position,
            caption=entry["caption"],
            target_id=entry["document_id"],
        )
        for position, entry in enumerate(item["items"])
    )


def _check_references(document: Document, sections: list[dict]) -> None:
    """Every file and attachment target in the payload must be real, and belong
    where it says it does. Both are checked in one query each."""
    file_ids = {fid for s in sections if s["type"] == SectionType.LONG_EXPLANATION for fid in s["file_ids"]}
    if file_ids:
        found = set(document.files.filter(id__in=file_ids).values_list("id", flat=True))
        if found != file_ids:
            raise ValidationError({"sections": ["فایل انتخاب‌شده متعلق به این مستند نیست یا حذف شده است."]})

    target_ids = {
        entry["document_id"]
        for s in sections
        if s["type"] == SectionType.ATTACHMENT
        for entry in s["items"]
    }
    if target_ids:
        if document.pk in target_ids:
            raise ValidationError({"sections": ["یک مستند نمی‌تواند خودش را ضمیمه کند."]})
        found = set(Document.objects.filter(id__in=target_ids).values_list("id", flat=True))
        if found != target_ids:
            raise ValidationError({"sections": ["مستند انتخاب‌شده به‌عنوان ضمیمه یافت نشد."]})


@transaction.atomic
def save_content(*, user, document_id: int, data: dict) -> Document:
    """Replace a draft's body with `data` (already validated).

    Sections carrying the `id` of an existing section are updated in place, the
    rest are created, and existing sections missing from the payload are deleted —
    so a reorder is just new positions, and change-table rows keep their identity
    (and therefore their dates) across saves.
    """
    document = _locked(document_id)
    _require_editable(document)

    if data["base_version"] != document.content_version:
        raise ConflictError(
            "این مستند در همین فاصله توسط شخص دیگری ذخیره شده است. صفحه را بازخوانی کنید.",
            code="version_conflict",
            current_version=document.content_version,
        )

    sections = data["sections"]
    _check_references(document, sections)

    existing = {s.id: s for s in document.sections.all()}
    today = timezone.localdate()
    keep = set()

    for position, item in enumerate(sections):
        section = existing.get(item.get("id"))
        if section is None or section.type != item["type"]:
            # An unknown id is a section deleted since the client loaded it;
            # treat it as new rather than failing the whole save.
            section = Section(document=document, type=item["type"])
        section.position = position
        section.content = _section_content(item)
        section.save()
        keep.add(section.id)

        kind = item["type"]
        if kind == SectionType.LONG_EXPLANATION:
            section.files.set(item["file_ids"])
        elif kind == SectionType.RESPONSIBILITIES:
            _sync_responsibilities(section, item)
        elif kind == SectionType.CHANGES_TABLE:
            _sync_changes(section, item, today)
        elif kind == SectionType.ATTACHMENT:
            _sync_attachments(section, item)

    document.sections.exclude(id__in=keep).delete()

    document.footnote1 = data["footnote1"]
    document.footnote2 = data["footnote2"]
    document.content_version += 1
    document.content_saved_at = timezone.now()
    document.save(update_fields=["footnote1", "footnote2", "content_version", "content_saved_at", "updated_at"])

    # Files nobody references any more (removed from their block, or uploaded and
    # then abandoned) are deleted with the save that orphaned them.
    for orphan in document.files.filter(sections__isnull=True):
        _delete_storage_on_commit(orphan.file)
        orphan.delete()

    return document


# --------------------------------------------------------------------------
# Uploads
# --------------------------------------------------------------------------


@transaction.atomic
def add_file(*, user, document_id: int, upload) -> tuple[DocumentFile, bool]:
    """Store an uploaded file against a draft. Returns (file, created); uploading
    the same bytes again returns the existing record rather than a duplicate."""
    document = _locked(document_id)
    _require_editable(document)

    kind, digest, size = inspect_upload(upload)
    existing = document.files.filter(sha256=digest).first()
    if existing is not None:
        return existing, False

    record = DocumentFile(
        document=document,
        original_name=upload.name[:255],
        kind=kind,
        size=size,
        sha256=digest,
        uploaded_by=user,
    )
    record.file.save(upload.name, upload, save=False)
    try:
        with transaction.atomic():
            record.save()
    except IntegrityError:  # a concurrent upload of the same bytes won the race
        _delete_storage_on_commit(record.file)
        return document.files.get(sha256=digest), False
    return record, True


@transaction.atomic
def set_logo(*, document_id: int, upload) -> Document:
    document = _locked(document_id)
    _require_editable(document)
    png = normalize_logo(upload)
    _delete_storage_on_commit(document.logo)
    document.logo.save("logo.png", png, save=False)
    document.save(update_fields=["logo", "updated_at"])
    return document


@transaction.atomic
def remove_logo(*, document_id: int) -> Document:
    document = _locked(document_id)
    _require_editable(document)
    _delete_storage_on_commit(document.logo)
    document.logo = ""
    document.save(update_fields=["logo", "updated_at"])
    return document


# --------------------------------------------------------------------------
# Copy-forward for a new revision
# --------------------------------------------------------------------------


def _copy_stored_file(source_field, target_field, name: str) -> None:
    # Streamed through a File wrapper so a large video isn't read into memory.
    with source_field.open("rb") as handle:
        target_field.save(name, File(handle), save=False)


def copy_content(source: Document, target: Document) -> None:
    """Start `target` (a fresh draft revision) as a copy of `source`'s body.

    Copied: footnotes, logo, uploaded files (physically — a shared file would be
    deleted out from under one revision by an edit to the other), every section,
    responsibilities, and attachment references.

    Deliberately NOT copied: change-table rows. Earlier revisions' rows are
    already visible to the new revision through the revision chain
    (`Document.previous_change_rows`); copying them as well would show each twice.
    The new revision's Changes Table block starts empty, ready for this edition's
    changes.
    """
    target.footnote1, target.footnote2 = source.footnote1, source.footnote2
    if source.logo:
        _copy_stored_file(source.logo, target.logo, "logo.png")
    target.save(update_fields=["footnote1", "footnote2", "logo", "updated_at"])

    file_map = {}
    for old in source.files.all():
        new = DocumentFile(
            document=target,
            original_name=old.original_name,
            kind=old.kind,
            size=old.size,
            sha256=old.sha256,
            uploaded_by=old.uploaded_by,
        )
        _copy_stored_file(old.file, new.file, old.original_name)
        new.save()
        file_map[old.id] = new

    for old_section in source.sections.all():
        section = Section.objects.create(
            document=target,
            position=old_section.position,
            type=old_section.type,
            content=old_section.content,
        )
        kind = old_section.type
        if kind == SectionType.LONG_EXPLANATION:
            section.files.set([file_map[f.id] for f in old_section.files.all() if f.id in file_map])
        elif kind == SectionType.RESPONSIBILITIES:
            ResponsibilityRow.objects.bulk_create(
                ResponsibilityRow(
                    section=section,
                    position=row.position,
                    role=row.role,
                    post=row.post,
                    supervisor=row.supervisor,
                    text=row.text,
                )
                for row in old_section.responsibility_rows.all()
            )
        elif kind == SectionType.ATTACHMENT:
            AttachmentReference.objects.bulk_create(
                AttachmentReference(
                    section=section,
                    position=item.position,
                    caption=item.caption,
                    target_id=item.target_id,
                )
                for item in old_section.attachment_items.all()
            )
