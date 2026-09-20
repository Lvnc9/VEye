"""Plan and write an import (Phase 6) — the part that touches Postgres.

Decided with the user:
* **collisions**: a document whose code+revision (or title) already exists is *skipped
  and reported*, never overwritten; re-running is therefore safe (idempotent);
* **dry-run by default**: the same code path runs, everything is parsed and checked,
  and the report says what *would* happen, but nothing is written;
* **local files only**: bodies come from `saves/`, images from `img/`; anything that
  isn't there is reported as not migrated — never fetched over the network.

Rules that come from V_2's own model (see docs/skeleton.md "Notes for the Phase 6
importer"): numbers and revisions from the stored codes (never `simple_code`), status
from `valid` (V_1.0 never wrote `status`), Arabic/Persian letters normalised in titles,
`DocumentSequence` raised to the highest imported number, and — because V_1.0 never
marked a superseded revision — an earlier UNDER_CONTROL revision that has a later
UNDER_CONTROL one in the same batch is imported as OBSOLETE, as V_2's approval would
have made it (reported per document).
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from django.core.files.base import ContentFile
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.accounts.models import AccessLevel, AccessRoll, User
from apps.core.constants import (
    RESPONSIBILITY_ROLE_ORDER,
    DocumentEventKind,
    DocumentStatus,
    SectionType,
)
from apps.documents.files import normalize_logo, normalize_signature
from apps.documents.models import (
    AttachmentReference,
    ChangeTableRow,
    Document,
    DocumentEvent,
    DocumentSequence,
    ResponsibilityRow,
    Section,
    SignOff,
)

from . import mapping
from .files import V1Files
from .mapping import IndexRecord, Note, RowError

logger = logging.getLogger("veye")

#: The account that owns every imported document (`created_by` is required). Inactive, no
#: usable password: it can never sign in.
IMPORT_USER_CODE = "v1-import"
IMPORT_USER_NAME = "واردسازی از نسخهٔ ۱"

TEHRAN = ZoneInfo("Asia/Tehran")
FINAL_STATUSES = (DocumentStatus.UNDER_CONTROL, DocumentStatus.OBSOLETE)


@dataclass
class Entry:
    """One line of the report."""

    position: int
    code: str
    title: str
    action: str = "pending"   # would_create | created | skipped | error
    notes: list = field(default_factory=list)

    def add(self, note: Note):
        self.notes.append(note)

    def as_dict(self) -> dict:
        return {
            "position": self.position,
            "code": self.code,
            "title": self.title,
            "action": self.action,
            "notes": [{"level": n.level, "code": n.code, "message": n.message} for n in self.notes],
        }


@dataclass
class Planned:
    record: IndexRecord
    entry: Entry
    content: mapping.ContentRecord | None = None
    status: str = ""


def import_user() -> User:
    user, created = User.objects.get_or_create(
        national_code=IMPORT_USER_CODE,
        defaults=dict(
            full_name=IMPORT_USER_NAME,
            access_roll=AccessRoll.GUILD,
            access_level=AccessLevel.LEVEL_3,
            is_active=False,
        ),
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    return user


def _noon(day):
    return datetime.combine(day, time(12, 0), tzinfo=TEHRAN)


# --------------------------------------------------------------------------
# Planning (no writes)
# --------------------------------------------------------------------------


def _content_matches(record: IndexRecord, document_number) -> bool:
    """Guard against a content file that belongs to another document. V_1.0 stamped the
    number "…-00" on a revision-1 file before it was first saved, so that is accepted."""
    parsed = mapping.parse_document_code(document_number)
    if parsed is None:
        return True  # nothing to compare
    group, number, revision = parsed
    if (group, number) != record.family:
        return False
    return revision == record.revision or (revision == 0 and record.revision == 1)


def read_content(record: IndexRecord, files: V1Files, entry: Entry):
    """The document's content record, or None (with a note saying why)."""
    finalized = record.status in FINAL_STATUSES
    names = [record.json_name] if record.json_name else []
    names.append(f"{record.title}-{record.full_code}.json")  # V_1.0's own naming, as a fallback
    data, reason = None, "missing"
    for name in names:
        data, reason = files.read_json(name)
        if data is not None:
            break
    if data is None:
        if reason == "missing" and not record.json_name and not finalized:
            entry.add(Note("info", "no_content", "این پیش‌نویس هنوز محتوایی ذخیره نکرده بود."))
        else:
            level = "warning" if finalized or record.json_name else "info"
            why = {"missing": "فایل محتوا در پوشهٔ saves یافت نشد", "too_large": "فایل محتوا بیش از حد بزرگ است",
                   "unreadable": "فایل محتوا خوانده نشد"}[reason]
            entry.add(Note(level, "content_missing", f"{why}؛ مستند بدون محتوا وارد شد."))
        return None

    if not _content_matches(record, data.get("document_number") if isinstance(data, dict) else None):
        entry.add(Note("warning", "content_mismatch",
                       f"فایل محتوا متعلق به مستند دیگری است ({data.get('document_number')}); محتوا وارد نشد."))
        return None
    content = mapping.map_content(data)
    for note in content.notes:
        entry.add(note)
    return content


def plan(rows: list, files: V1Files):
    """Map every row, read its content, and decide statuses. Returns (planned, entries):
    `planned` are the importable records in family order; `entries` is every report line
    (including rows that could not be mapped)."""
    entries, planned, seen = [], [], {}
    for position, row in enumerate(rows, start=1):
        try:
            record = mapping.map_index_row(row, position)
        except RowError as error:
            title = mapping.clean(row.get("title")) if isinstance(row, dict) else ""
            entry = Entry(position, mapping.clean(row.get("code")) if isinstance(row, dict) else "", title, "error")
            entry.add(error.note)
            entries.append(entry)
            continue

        entry = Entry(position, record.full_code, record.title)
        for note in record.notes:
            entry.add(note)
        key = (record.group, record.number, record.revision)
        if key in seen:
            entry.action = "error"
            entry.add(Note("error", "duplicate_in_source", f"این بازنگری قبلاً در ردیف {seen[key]} آمده است؛ نادیده گرفته شد."))
            entries.append(entry)
            continue
        seen[key] = position
        entries.append(entry)
        planned.append(Planned(record, entry, status=record.status))

    planned.sort(key=lambda p: (p.record.prefix, p.record.number, p.record.revision))
    _supersede(planned)
    for item in planned:
        item.content = read_content(item.record, files, item.entry)
    return planned, entries


def _supersede(planned: list):
    """V_1.0 never marked an old revision superseded; V_2 does when the next one is
    approved. Apply that to the batch: an UNDER_CONTROL revision with a later
    UNDER_CONTROL revision of the same document is imported as OBSOLETE."""
    by_family = {}
    for item in planned:
        by_family.setdefault(item.record.family, []).append(item)
    for family in by_family.values():
        family.sort(key=lambda p: p.record.revision)
        for index, item in enumerate(family):
            later_valid = any(other.status == DocumentStatus.UNDER_CONTROL for other in family[index + 1:])
            if item.status == DocumentStatus.UNDER_CONTROL and later_valid:
                item.status = DocumentStatus.OBSOLETE
                item.entry.add(Note("info", "superseded_on_import",
                                    "بازنگری جدیدتری تحت کنترل است؛ این بازنگری «منسوخ» وارد شد."))


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------


def _image(reader, name: str, entry: Entry, what: str, normalizer):
    """A normalised PNG ContentFile for `img/<name>`, or None (with a note)."""
    if not name:
        return None
    data, reason = reader(name)
    if data is None:
        entry.add(Note("warning", f"{what}_missing", f"تصویر {what == 'logo' and 'لوگو' or 'امضا'} «{name}» در پوشهٔ img یافت نشد."))
        return None
    upload = ContentFile(data, name=name)
    try:
        return normalizer(upload)
    except ValidationError as error:
        detail = error.detail
        text = next(iter(detail.values()))[0] if isinstance(detail, dict) else str(detail)
        entry.add(Note("warning", f"{what}_unreadable", f"تصویر «{name}» وارد نشد: {text}"))
        return None


def _signers(item: Planned, files: V1Files):
    """[(SignerRecord, png ContentFile | None, signed_date)] for a finalized document."""
    record, content, entry = item.record, item.content, item.entry
    signers = {s.role: s for s in (content.signers if content else [])}
    for role, (name, when) in record.index_signers.items():   # the index row's [name, date] shape
        signers.setdefault(role, mapping.SignerRecord(role, name, "", ""))
    if item.status not in FINAL_STATUSES:
        if signers:
            entry.add(Note("info", "signers_ignored_on_draft", "امضاهای ثبت‌شده برای پیش‌نویس وارد نشد."))
        return []
    fallback = content.date if content else None
    result = []
    for role in ("creater", "confirmer", "approver"):
        signer = signers.get(role)
        if signer is None:
            continue
        signed_on = fallback
        if role in record.index_signers:
            signed_on = mapping.parse_jalali(record.index_signers[role][1]) or fallback
        png = _image(files.read_image, signer.signature_name, entry, "signature", normalize_signature)
        result.append((signer, png, signed_on))
    if not result:
        entry.add(Note("warning", "no_signers", "برای این مستند هیچ امضایی ثبت نشده بود."))
    return result


def _write_sections(document: Document, content: mapping.ContentRecord):
    for position, (kind, payload) in enumerate(content.sections):
        if kind == SectionType.SHORT_EXPLANATION:
            Section.objects.create(document=document, position=position, type=kind, content={"lines": payload["lines"]})
        elif kind == SectionType.LONG_EXPLANATION:
            Section.objects.create(document=document, position=position, type=kind, content=payload)
        elif kind == SectionType.RESPONSIBILITIES:
            section = Section.objects.create(document=document, position=position, type=kind)
            rows = [
                ResponsibilityRow(section=section, position=i, role=r["role"], post=r["post"],
                                  supervisor=r["supervisor"], text=r["text"])
                for i, r in enumerate(payload["roles"])
            ]
            offset = len(RESPONSIBILITY_ROLE_ORDER)
            rows += [ResponsibilityRow(section=section, position=offset + i, text=text)
                     for i, text in enumerate(payload["notes"])]
            ResponsibilityRow.objects.bulk_create(rows)
        elif kind == SectionType.CHANGES_TABLE:
            section = Section.objects.create(document=document, position=position, type=kind)
            ChangeTableRow.objects.bulk_create(
                ChangeTableRow(section=section, position=i, text=row["text"], date=row["date"])
                for i, row in enumerate(payload["rows"])
            )
        elif kind == SectionType.ATTACHMENT:
            # Targets may be imported later in this same run; filled in by _link_attachments.
            Section.objects.create(document=document, position=position, type=kind)


def _create_document(item: Planned, owner: User, run_id, files: V1Files, previous: Document | None, saved_files: list):
    record, content, entry = item.record, item.content, item.entry
    when = _noon(content.date) if content and content.date else None
    document = Document.objects.create(
        category=record.category, title=record.title, group=record.group, number=record.number,
        revision=record.revision, status=item.status, created_by=owner,
        previous_revision=previous,
        content_saved_at=when if content else None,
        footnote1=content.footnote1 if content else "", footnote2=content.footnote2 if content else "",
    )
    if when:
        # Keep the register/history ordering meaningful: the document dates from when V_1.0 saved it.
        Document.objects.filter(pk=document.pk).update(created_at=when)

    if content:
        logo = _image(files.read_image, content.logo_name, entry, "logo", normalize_logo)
        if logo is not None:
            document.logo.save("logo.png", logo, save=False)
            document.save(update_fields=["logo"])
            saved_files.append(document.logo)
        _write_sections(document, content)

    for signer, png, signed_on in _signers(item, files):
        signoff = SignOff(document=document, role=signer.role, name=signer.name, position=signer.position, signed_date=signed_on)
        if png is not None:
            signoff.signature.save("signature.png", png, save=False)
            saved_files.append(signoff.signature)
        signoff.save()

    DocumentEvent.objects.create(
        document=document, kind=DocumentEventKind.IMPORTED, from_status=item.status, to_status=item.status,
        actor=None, actor_name=IMPORT_USER_NAME, actor_title="",
        reason=f"واردشده از نسخهٔ ۱ (اجرای واردسازی شمارهٔ {run_id})" if run_id else "واردشده از نسخهٔ ۱",
    )
    return document


def _link_attachments(created: dict, lookup):
    """Second pass, once every document of the run exists: point each Attachment block at
    the documents its «CODE-REV» labels name. Unresolvable ones are reported and dropped."""
    for item, document in created.values():
        if not item.content or not item.content.attachments:
            continue
        # One Attachment block per document (the designer enforces it; the mapper keeps the first).
        section = document.sections.filter(type=SectionType.ATTACHMENT).order_by("position", "id").first()
        if section is None:
            continue
        position = 0
        for caption, code in item.content.attachments:
            target = lookup(code)
            if target is None:
                item.entry.add(Note("warning", "attachment_unresolved", f"ضمیمهٔ «{caption}» به مستند {code} اشاره می‌کرد که یافت نشد."))
            elif target.pk == document.pk:
                item.entry.add(Note("warning", "attachment_self", f"ضمیمهٔ «{caption}» به خود مستند اشاره می‌کرد؛ وارد نشد."))
            else:
                AttachmentReference.objects.create(section=section, position=position, caption=caption, target=target)
                position += 1


def _delete_files(fields):
    for field_file in fields:
        try:
            if field_file and field_file.name:
                field_file.storage.delete(field_file.name)
        except Exception:  # noqa: BLE001 — best-effort cleanup of files from a rolled-back document
            logger.warning("import: could not remove %s", getattr(field_file, "name", "?"))


# --------------------------------------------------------------------------
# The run
# --------------------------------------------------------------------------


@dataclass
class Result:
    counts: dict
    entries: list


def run_import(rows: list, files: V1Files, *, dry_run: bool, run_id=None, progress=None) -> Result:
    """Import `rows` (index rows) with content/images from `files`. `progress(done, total)`
    is called after each document. With `dry_run` nothing is written.

    A real run writes inside ONE outer transaction, with a savepoint per document: a
    document that fails is rolled back alone and reported, while a failure of the run
    itself (linking attachments, the sequence bump, the database going away) rolls back
    everything — so an import is never left half-done — and removes the files it wrote."""
    planned, entries = plan(rows, files)

    if dry_run:
        counts = _plan_only(planned, entries, files, len(rows), progress)
    else:
        written: list = []  # every stored file (logo/signature) this run created
        try:
            with transaction.atomic():
                counts = _write(planned, entries, files, len(rows), run_id, progress, written)
        except BaseException:
            _delete_files(written)
            raise

    counts["warnings"] = sum(1 for e in entries for n in e.notes if n.level == "warning")
    return Result(counts, entries)


def _base_counts(entries: list, total_rows: int) -> dict:
    return {
        "total": total_rows, "created": 0, "would_create": 0, "skipped": 0,
        "errors": sum(1 for e in entries if e.action == "error"), "superseded": 0,
    }


def _collision(item: Planned, existing: dict, taken_titles: set):
    """The reason a planned document must be skipped (or None). Existing rows are never touched."""
    record, entry = item.record, item.entry
    if (record.group, record.number, record.revision) in existing:
        entry.add(Note("info", "exists", "این بازنگری از قبل در سامانه وجود دارد؛ دست نخورد."))
        return "exists"
    if record.revision == 1 and (record.group, record.title) in taken_titles:
        entry.add(Note("warning", "title_conflict", "مستند دیگری در همین گروه با همین عنوان وجود دارد؛ وارد نشد."))
        return "title_conflict"
    return None


def _plan_only(planned, entries, files, total_rows, progress) -> dict:
    """The dry run: everything is checked, nothing is written."""
    existing = {(d.group, d.number, d.revision): d for d in Document.objects.all()}
    taken_titles = {(d.group, d.title) for d in existing.values() if d.revision == 1}
    counts = _base_counts(entries, total_rows)
    pending: set = set()

    for done, item in enumerate(planned, start=1):
        record, entry = item.record, item.entry
        if _collision(item, existing, taken_titles):
            entry.action = "skipped"
            counts["skipped"] += 1
        else:
            entry.action = "would_create"
            counts["would_create"] += 1
            pending.add((record.group, record.number, record.revision))
            # Run the same content/image handling so the report shows missing images.
            _signers(item, files)
            if item.content:
                _image(files.read_image, item.content.logo_name, entry, "logo", normalize_logo)
            if record.revision == 1:
                taken_titles.add((record.group, record.title))
            if item.status != record.status:
                counts["superseded"] += 1
        if progress:
            progress(done, len(planned))

    _report_attachments_dry(planned, existing, pending)
    return counts


def _write(planned, entries, files, total_rows, run_id, progress, written) -> dict:
    existing = {(d.group, d.number, d.revision): d for d in Document.objects.all()}
    taken_titles = {(d.group, d.title) for d in existing.values() if d.revision == 1}
    counts = _base_counts(entries, total_rows)
    owner = import_user()
    created: dict = {}  # key -> (Planned, Document)

    for done, item in enumerate(planned, start=1):
        record, entry = item.record, item.entry
        key = (record.group, record.number, record.revision)
        if _collision(item, existing, taken_titles):
            entry.action = "skipped"
            counts["skipped"] += 1
        else:
            previous = _nearest_previous(record, existing, created)
            saved_files: list = []
            try:
                with transaction.atomic():  # a savepoint: only this document rolls back
                    document = _create_document(item, owner, run_id, files, previous, saved_files)
            except Exception as error:  # noqa: BLE001 — one bad document must not stop the run
                _delete_files(saved_files)
                logger.exception("import: document %s failed", record.full_code)
                entry.action = "error"
                entry.add(Note("error", "import_failed", f"وارد کردن این مستند ناموفق بود ({type(error).__name__}); بقیه ادامه یافتند."))
                counts["errors"] += 1
            else:
                written.extend(saved_files)
                entry.action = "created"
                counts["created"] += 1
                created[key] = (item, document)
                if record.revision == 1:
                    taken_titles.add((record.group, record.title))
                if item.status != record.status:
                    counts["superseded"] += 1
        if progress:
            progress(done, len(planned))

    def lookup(code):
        key = mapping.parse_document_code(code)
        if key is None:
            return None
        return created[key][1] if key in created else existing.get(key)

    _link_attachments(created, lookup)
    _raise_sequences(list(existing.values()) + [d for _, d in created.values()])
    return counts


def _nearest_previous(record: IndexRecord, existing: dict, created: dict):
    """The closest lower revision of the same document, if it has no successor yet
    (`previous_revision` is one-to-one: a revision has at most one successor)."""
    lower = [k for k in list(existing) + list(created)
             if k[0] == record.group and k[1] == record.number and k[2] < record.revision]
    if not lower:
        return None
    key = max(lower, key=lambda k: k[2])
    candidate = created[key][1] if key in created else existing[key]
    return None if Document.objects.filter(previous_revision=candidate).exists() else candidate


def _report_attachments_dry(planned: list, existing: dict, pending: set):
    for item in planned:
        if item.entry.action != "would_create" or not item.content:
            continue
        for caption, code in item.content.attachments:
            key = mapping.parse_document_code(code)
            if key is None or not (key in existing or key in pending):
                item.entry.add(Note("warning", "attachment_unresolved", f"ضمیمهٔ «{caption}» به مستند {code} اشاره می‌کرد که یافت نشد."))


def _raise_sequences(documents: list):
    """Make the next new document in each group number after everything imported."""
    highest = {}
    for document in documents:
        highest[document.group] = max(highest.get(document.group, 0), document.number)
    for group, number in highest.items():
        sequence, _ = DocumentSequence.objects.select_for_update().get_or_create(group=group)
        if sequence.last_number < number:
            sequence.last_number = number
            sequence.save(update_fields=["last_number"])
