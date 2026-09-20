"""V_1.0 -> V_2 record mapping (pure functions: no database, no files, no network).

Two inputs per document, as V_1.0 kept them:

* an **index row** from MongoDB (`my_database.my_collection`, written by
  documents_01.py:714-733): category, title, group, `review` ("0-0" = never saved,
  otherwise "tens-units"), `code` ("PO-01"), `valid` ("unknown" / "vali" / "outdated"),
  `json_path` (a Liara URL of the content file) …
* the **content JSON** saved next to it (utils.py:507-655): header fields, signers and
  `dynamic_items`.

Every rule here comes from `docs/skeleton.md` "Notes for the Phase 6 importer" and from
what the real V_1.0 files look like. Nothing is guessed silently: anything that can't be
mapped becomes a `Note` that ends up in the import report.
"""
import re
from dataclasses import dataclass, field
import datetime as dt
from urllib.parse import unquote, urlparse

import jdatetime

from apps.core.constants import (
    GROUP_CODE_PREFIX,
    LEGACY_CATEGORY_VALUES,
    RESPONSIBILITY_ROLE_ORDER,
    DocumentCategory,
    DocumentGroup,
    DocumentStatus,
    SectionType,
    SignOffRole,
)
from apps.core.text import normalize_letters, normalize_title

MAX_REVISION = 99

#: The two dropdown placeholders V_1.0 saved in essentially every Responsibilities block
#: (utils.py:1452,1476) — they are "no value", not values.
RESPONSIBILITY_PLACEHOLDERS = {"organiztion post", "supervisor", "organization post"}

_CODE = re.compile(r"^([A-Za-z]{2})-(\d+)$")
_REVIEW = re.compile(r"^(\d+)\s*-\s*(\d+)$")
_DOCUMENT_NUMBER = re.compile(r"^([A-Za-z]{2})-(\d+)-(\d{1,2})$")

#: Persian group label (letters normalised) -> DocumentGroup.
_GROUP_BY_LABEL = {normalize_letters(label): group for group, label in DocumentGroup.choices}
_PREFIX_TO_GROUP = {prefix: group for group, prefix in GROUP_CODE_PREFIX.items()}


@dataclass(frozen=True)
class Note:
    """One thing the operator should know about a document (goes into the report)."""

    level: str  # "info" | "warning" | "error"
    code: str
    message: str  # Persian


class RowError(Exception):
    """A row that cannot be imported at all."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.note = Note("error", code, message)


@dataclass
class IndexRecord:
    """A document as the MongoDB index row describes it."""

    position: int                      # row number in the source (1-based), for the report
    title: str
    group: str                         # DocumentGroup value
    category: str                      # DocumentCategory value
    number: int
    revision: int
    status: str                        # DocumentStatus value (before supersede normalisation)
    json_name: str                     # content file name from json_path ("" = never saved)
    index_signers: dict = field(default_factory=dict)   # role -> [name, date] (overwritten shape)
    notes: list = field(default_factory=list)

    @property
    def prefix(self) -> str:
        return GROUP_CODE_PREFIX[self.group]

    @property
    def full_code(self) -> str:
        return f"{self.prefix}-{self.number:02d}-{self.revision:02d}"

    @property
    def family(self) -> tuple:
        return (self.group, self.number)


@dataclass
class SignerRecord:
    role: str
    name: str
    position: str
    signature_name: str  # image file name ("" = none)


@dataclass
class ContentRecord:
    """The body and header of a document, from its content JSON."""

    date: dt.date | None = None
    logo_name: str = ""
    footnote1: str = ""
    footnote2: str = ""
    sections: list = field(default_factory=list)   # [(SectionType, payload)]
    signers: list = field(default_factory=list)    # [SignerRecord]
    attachments: list = field(default_factory=list)  # [(caption, "PR-01-01")] resolved later
    notes: list = field(default_factory=list)


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------


def clean(value) -> str:
    """A stored string, or "" for None / non-strings."""
    return value.strip() if isinstance(value, str) else ""


def basename_from_url(value) -> str:
    """The file name at the end of a Liara URL (`.../user-files/PR-01-00creater.png`),
    percent-decoded. Only the last path segment is ever used, so no path a row or JSON
    supplies can point outside the import directory."""
    text = clean(value)
    if not text:
        return ""
    path = urlparse(text).path if "://" in text else text
    name = unquote(path.replace("\\", "/").rsplit("/", 1)[-1]).strip()
    return "" if name in ("", ".", "..") else name


def parse_jalali(value) -> dt.date | None:
    """`1404/01/19` -> a Gregorian date, or None if it isn't a valid Jalali date."""
    text = clean(value)
    match = re.fullmatch(r"(\d{4})\s*[/-]\s*(\d{1,2})\s*[/-]\s*(\d{1,2})", text)
    if not match:
        return None
    try:
        return jdatetime.date(*map(int, match.groups())).togregorian()
    except ValueError:
        return None


# --------------------------------------------------------------------------
# The index row
# --------------------------------------------------------------------------


def status_for(valid: str, review: str) -> tuple[str, list]:
    """V_1.0 wrote the status only in `valid`: "vali" (its typo for valid) and
    "outdated" once saved to PDF, "unknown" before. `status` itself was never written."""
    notes = []
    value = clean(valid).lower()
    if value == "vali":
        status = DocumentStatus.UNDER_CONTROL
    elif value == "outdated":
        status = DocumentStatus.OBSOLETE
    else:
        status = DocumentStatus.DRAFT
        if value not in ("unknown", ""):
            notes.append(Note("warning", "unknown_valid", f"مقدار «valid» ناشناخته است ({valid!r}); به‌عنوان پیش‌نویس وارد شد."))
    return status, notes


def revision_for(review: str) -> tuple[int, bool]:
    """`review` is "tens-units": "0-0" = never saved (V_2 shows revision 01 + DRAFT),
    "0-1" = 1, "1-0" = 10. Returns (revision, is_never_saved)."""
    match = _REVIEW.match(clean(review))
    if not match:
        raise RowError("bad_review", f"شمارهٔ بازنگری نامعتبر است ({review!r}).")
    tens, units = int(match.group(1)), int(match.group(2))
    if tens == 0 and units == 0:
        return 1, True
    revision = 10 * tens + units
    if not 1 <= revision <= MAX_REVISION:
        raise RowError("revision_out_of_range", f"شمارهٔ بازنگری {revision} خارج از محدودهٔ ۱ تا {MAX_REVISION} است.")
    return revision, False


def map_index_row(row: dict, position: int) -> IndexRecord:
    """MongoDB index row -> IndexRecord, or RowError."""
    if not isinstance(row, dict):
        raise RowError("bad_row", "ردیف نامعتبر است.")

    title = normalize_title(clean(row.get("title")))
    if not title:
        raise RowError("missing_title", "عنوان مستند خالی است.")

    group_label = normalize_letters(clean(row.get("group")))
    group = _GROUP_BY_LABEL.get(group_label)
    if group is None and group_label in DocumentGroup.values:
        group = group_label
    if group is None:
        raise RowError("unknown_group", f"گروه مستند ناشناخته است ({row.get('group')!r}).")

    # `code` is the family code ("PO-01"). `simple_code` is *not* trusted: V_1.0 stored it
    # wrongly after any revision (documents_01.py:694 vs :780).
    code_match = _CODE.match(clean(row.get("code")))
    if not code_match:
        raise RowError("bad_code", f"کد مستند نامعتبر است ({row.get('code')!r}).")
    prefix, number = code_match.group(1).upper(), int(code_match.group(2))
    if number < 1:
        raise RowError("bad_code", f"شمارهٔ مستند نامعتبر است ({row.get('code')!r}).")
    if prefix != GROUP_CODE_PREFIX[group]:
        raise RowError(
            "code_group_mismatch",
            f"پیشوند کد ({prefix}) با گروه «{DocumentGroup(group).label}» ({GROUP_CODE_PREFIX[group]}) هم‌خوان نیست.",
        )

    revision, never_saved = revision_for(row.get("review"))
    status, notes = status_for(row.get("valid"), row.get("review"))
    if never_saved and status != DocumentStatus.DRAFT:
        notes.append(Note("warning", "valid_but_never_saved", "بازنگری «۰-۰» است ولی معتبر ثبت شده؛ به‌عنوان پیش‌نویس وارد شد."))
        status = DocumentStatus.DRAFT

    raw_category = clean(row.get("category"))
    if raw_category in LEGACY_CATEGORY_VALUES:
        category = LEGACY_CATEGORY_VALUES[raw_category]
    elif raw_category in DocumentCategory.values:
        category = raw_category
    else:
        category = DocumentCategory.INSIDE
        notes.append(Note("warning", "unknown_category", f"دسته‌بندی ناشناخته است ({raw_category!r}); «داخل سازمانی» در نظر گرفته شد."))

    signers = {}
    for role in SignOffRole.values:
        entry = row.get(role)
        if isinstance(entry, list) and entry and clean(entry[0]):
            signers[role] = [clean(entry[0]), clean(entry[1]) if len(entry) > 1 else ""]

    return IndexRecord(
        position=position, title=title, group=group, category=category, number=number,
        revision=revision, status=status, json_name=basename_from_url(row.get("json_path")),
        index_signers=signers, notes=notes,
    )


# --------------------------------------------------------------------------
# The content JSON
# --------------------------------------------------------------------------


def _text_list(value) -> list:
    return [str(item) for item in value] if isinstance(value, list) else []


def _responsibilities(content: dict, notes: list) -> dict:
    """`options` is 8 slots (post i, supervisor i+4); `entries[i]` the text of row i and
    `entries[4:]` description-only notes (utils.py:1373-1403 / 574-594)."""
    options = _text_list(content.get("options")) + [""] * 8
    entries = _text_list(content.get("entries"))
    roles = []
    for index, role in enumerate(RESPONSIBILITY_ROLE_ORDER):
        post, supervisor = clean(options[index]), clean(options[index + 4])
        roles.append(
            {
                "role": role,
                "post": "" if post.lower() in RESPONSIBILITY_PLACEHOLDERS else post,
                "supervisor": "" if supervisor.lower() in RESPONSIBILITY_PLACEHOLDERS else supervisor,
                "text": entries[index] if index < len(entries) else "",
            }
        )
    return {"roles": roles, "notes": [text for text in entries[len(RESPONSIBILITY_ROLE_ORDER):]]}


def _changes(content: dict, fallback: dt.date | None, notes: list) -> list:
    """Only the rows written in *this* revision. V_1.0 also saved the previous revision's
    rows back into the file as `type: "label"` rows; V_2 derives those from the revision
    chain (`Document.previous_change_rows()`), so they are not imported."""
    rows, frozen = [], 0
    for row in content.get("rows", []) if isinstance(content.get("rows"), list) else []:
        body = row.get("content") if isinstance(row, dict) else None
        if not isinstance(body, dict):
            continue
        if body.get("type") == "label":
            frozen += 1
            continue
        text = clean(body.get("text"))
        if not text:
            continue
        when = parse_jalali(row.get("date"))
        if when is None:
            when = fallback
            notes.append(Note("warning", "bad_change_date", f"تاریخ ردیف جدول تغییرات نامعتبر است ({row.get('date')!r}); از تاریخ مستند استفاده شد."))
        if when is None:
            notes.append(Note("warning", "change_row_dropped", "ردیف جدول تغییرات بدون تاریخ معتبر حذف شد."))
            continue
        rows.append({"date": when, "text": text})
    if frozen:
        notes.append(Note("info", "frozen_change_rows", f"{frozen} ردیف قدیمی جدول تغییرات وارد نشد (از بازنگری‌های قبلی محاسبه می‌شود)."))
    return rows


def map_content(data: dict) -> ContentRecord:
    """Content JSON -> ContentRecord. Never raises for odd data; notes say what was lost."""
    record = ContentRecord()
    if not isinstance(data, dict):
        record.notes.append(Note("error", "bad_content", "فایل محتوا ساختار معتبری ندارد."))
        return record

    record.date = parse_jalali(data.get("date"))
    record.logo_name = basename_from_url(data.get("logo_path"))
    footnotes = data.get("footnotes") if isinstance(data.get("footnotes"), dict) else {}
    record.footnote1 = clean(footnotes.get("footnote1"))
    record.footnote2 = clean(footnotes.get("footnote2"))

    for role in SignOffRole.values:
        entry = data.get(role)
        if isinstance(entry, list) and entry and clean(entry[0]):
            record.signers.append(
                SignerRecord(
                    role=role,
                    name=clean(entry[0]),
                    position=clean(entry[1]) if len(entry) > 1 else "",
                    signature_name=basename_from_url(entry[2]) if len(entry) > 2 else "",
                )
            )

    seen_single = set()
    links = 0
    for item in data.get("dynamic_items", []) if isinstance(data.get("dynamic_items"), list) else []:
        kind = item.get("type") if isinstance(item, dict) else None
        content = item.get("content") if isinstance(item, dict) else None
        if kind == "Short Explanation":
            record.sections.append((SectionType.SHORT_EXPLANATION, {"lines": _text_list(content)}))
        elif kind == "Long Explanation" and isinstance(content, dict):
            record.sections.append(
                (
                    SectionType.LONG_EXPLANATION,
                    {
                        "heading": clean(content.get("main_entry")),
                        "body": content.get("main_textbox") if isinstance(content.get("main_textbox"), str) else "",
                        "extra_boxes": _text_list(content.get("additional_textboxes")),
                    },
                )
            )
            links += len(_text_list(content.get("links")))
        elif kind in ("Responsibilities", "Changes Table") and isinstance(content, dict):
            if kind in seen_single:  # the designer allows one of each per document
                record.notes.append(Note("warning", "duplicate_block", f"بلوک «{kind}» تکراری بود و نادیده گرفته شد."))
                continue
            seen_single.add(kind)
            if kind == "Responsibilities":
                record.sections.append((SectionType.RESPONSIBILITIES, _responsibilities(content, record.notes)))
            else:
                record.sections.append((SectionType.CHANGES_TABLE, {"rows": _changes(content, record.date, record.notes)}))
        elif kind == "Attachment":
            labels = item.get("all_labels") if isinstance(item.get("all_labels"), list) else []
            items = []
            for label in labels:
                if isinstance(label, list) and len(label) >= 2 and clean(label[0]) and clean(label[1]):
                    items.append((clean(label[0]), clean(label[1]).upper()))
            record.sections.append((SectionType.ATTACHMENT, {"items": items}))
            record.attachments.extend(items)
        else:
            record.notes.append(Note("warning", "unknown_block", f"بلوک ناشناخته نادیده گرفته شد ({kind!r})."))

    if links:
        record.notes.append(
            Note("warning", "links_not_migrated",
                 f"{links} پیوند فایل (Liara) وارد نشد: فایل‌ها از روی نشانی دانلود نمی‌شوند.")
        )
    return record


def parse_document_code(value) -> tuple | None:
    """`PR-01-01` -> (group, number, revision), or None when it isn't a document code."""
    canonical = normalize_document_number(value)
    if canonical is None:
        return None
    prefix, number, revision = canonical.split("-")
    group = _PREFIX_TO_GROUP.get(prefix)
    return None if group is None else (group, int(number), int(revision))


def normalize_document_number(value) -> str | None:
    """`PR-01-01` (a content file's `document_number`) -> canonical `PR-01-01`, or None."""
    match = _DOCUMENT_NUMBER.match(clean(value))
    if not match:
        return None
    prefix, number, revision = match.groups()
    return f"{prefix.upper()}-{int(number):02d}-{int(revision):02d}"
