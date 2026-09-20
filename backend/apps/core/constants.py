"""Canonical domain vocabulary, ported from the live V_1.0 desktop app.

Every string here is load-bearing: the Persian labels are what users see and
what the original app matched on, and the Latin prefixes are what appear in
document codes and filenames. Sources are cited per-constant against the live
V_1.0 files (see .claude/skeleton.md for the live-vs-dead file list).
"""
from django.db import models


class DocumentGroup(models.TextChoices):
    """V_1.0: other_folder/documents_01.py:699-706.

    The Persian label does not transliterate to its Latin prefix — پوستر→PO is
    intuitive, but روش اجرایی→PR and دستورالعمل→WI are deliberately crossed.
    This mapping is reproduced literally from the original.
    """

    POSTER = "POSTER", "پوستر"
    PROCEDURE = "PROCEDURE", "روش اجرایی"
    INSTRUCTION = "INSTRUCTION", "دستورالعمل"
    FORM = "FORM", "فرم"


GROUP_CODE_PREFIX = {
    DocumentGroup.POSTER: "PO",
    DocumentGroup.PROCEDURE: "PR",
    DocumentGroup.INSTRUCTION: "WI",
    DocumentGroup.FORM: "FR",
}


class DocumentCategory(models.TextChoices):
    """V_1.0: other_folder/documents_01.py:1734 — the دسته بندی dropdown.

    The desktop app stores (and displays) these as the English strings
    'Inside Organization' / 'Outside Organization', unlike the groups, which
    are Persian. The Persian labels here are a translation for the Persian
    UI (the original's own search placeholder, documents_01.py:1597, already
    says «برون سازمانی»). See LEGACY_CATEGORY_VALUES for the import mapping.
    """

    INSIDE = "INSIDE", "داخل سازمانی"
    OUTSIDE = "OUTSIDE", "برون سازمانی"


#: Values as stored in V_1.0's MongoDB `category` field -> new enum value.
#: Used by the Phase 6 importer.
LEGACY_CATEGORY_VALUES = {
    "Inside Organization": DocumentCategory.INSIDE,
    "Outside Organization": DocumentCategory.OUTSIDE,
}


class DocumentStatus(models.TextChoices):
    """The five-state lifecycle.

    Taken from the Dashboard's column headers (V_1.0 other_folder/Dashboard.py:344-350),
    which is the state model the product actually wants. The desktop app only ever
    implemented a three-value `valid` field (unknown / "vali" / outdated) — note
    "vali" is a typo in the original and is deliberately not carried over.
    """

    DRAFT = "DRAFT", "پیش نویس"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION", "در انتظار تأیید"
    AWAITING_APPROVAL = "AWAITING_APPROVAL", "در انتظار تصویب"
    UNDER_CONTROL = "UNDER_CONTROL", "تحت کنترل"
    OBSOLETE = "OBSOLETE", "منسوخ شده"


class SignOffRole(models.TextChoices):
    """V_1.0 uses the misspelling "creater" throughout — as a DB field, a JSON
    key, a variable name, and in signature filenames (`PO-01-01creater.png`).
    The stored value keeps that spelling so migrated data and existing
    signature files line up; only the human-facing label is correct.
    """

    CREATER = "creater", "تدوین کننده"
    CONFIRMER = "confirmer", "تایید کننده"
    APPROVER = "approver", "تصویب کننده"


class DocumentEventKind(models.TextChoices):
    """The audit trail of a document's workflow (Phase 5). V_1.0 recorded none of
    this: its مرجوع button was a no-op and nothing captured who signed when."""

    SUBMITTED = "submitted", "ارسال برای تایید"
    CONFIRMED = "confirmed", "تایید شد"
    APPROVED = "approved", "تصویب شد"
    RETURNED = "returned", "مرجوع شد"
    SUPERSEDED = "superseded", "منسوخ شد (جایگزین شد)"


class ValidationMark(models.TextChoices):
    """Printed onto the PDF's control table (V_1.0 other_folder/to_make_pdf.py:997)."""

    VALID = "VALID", "معتبر"
    OBSOLETE = "OBSOLETE", "منسوخ"


class SectionType(models.TextChoices):
    """The five block types of `dynamic_items`, in the order they render.

    V_1.0: serialized by other_folder/utils.py:533-655, consumed by
    other_folder/deliver_convert.py:62-135. Stored values match the original
    JSON discriminators so migrated documents round-trip unchanged.
    """

    SHORT_EXPLANATION = "Short Explanation", "تشریحی کوتاه"
    LONG_EXPLANATION = "Long Explanation", "تشریحی بلند"
    RESPONSIBILITIES = "Responsibilities", "مسئولیت ها"
    CHANGES_TABLE = "Changes Table", "جدول تغییرات"
    ATTACHMENT = "Attachment", "ضمائم"


#: The letters the PDF prints beside the four Responsibility rows
#: (other_folder/deliver_convert.py:99-114).
RESPONSIBILITY_ROW_LABELS = ["الف", "ب", "ج", "د"]


class ResponsibilityRole(models.TextChoices):
    """The four fixed rows of a Responsibilities block, in V_1.0's on-screen
    order (other_folder/utils.py:1373-1403, where they are labeled Responder /
    Reciver / Cash Account / Supervisor). Each row carries a سمت (post), a ناظر
    (supervisor) and a description; V_1.0 stores them as a flat 8-slot `options`
    array — index i is the post, index i+4 the supervisor.
    """

    RESPONDER = "responder", "پاسخگو"
    RECEIVER = "receiver", "پاسخ‌خواه"
    CASH_ACCOUNT = "cash_account", "حسابکش"
    SUPERVISOR = "supervisor", "ناظر"


#: Row order, which is also the order the PDF letters الف/ب/ج/د are assigned.
RESPONSIBILITY_ROLE_ORDER = [
    ResponsibilityRole.RESPONDER,
    ResponsibilityRole.RECEIVER,
    ResponsibilityRole.CASH_ACCOUNT,
    ResponsibilityRole.SUPERVISOR,
]

#: Which row feeds which register column (حسابکش / پاسخ خواه / پاسخگو).
#:
#: V_1.0 filled them by *position* (utils.py:574-594: rows 1, 2, 3 -> accountant,
#: questioner, responder), which put the text typed in the row labeled
#: "Responder" under حسابکش and the "Cash Account" row under پاسخگو. The product
#: owner confirmed that was a swap and the columns should follow the row labels.
REGISTER_COLUMN_ROLE = {
    "accountant": ResponsibilityRole.CASH_ACCOUNT,
    "questioner": ResponsibilityRole.RECEIVER,
    "responder": ResponsibilityRole.RESPONDER,
}


class FileKind(models.TextChoices):
    """The three upload buttons of a Long Explanation block (Add Picture /
    Add File / Add Video, utils.py:1638-1666)."""

    PICTURE = "PICTURE", "تصویر"
    DOCUMENT = "DOCUMENT", "فایل"
    VIDEO = "VIDEO", "ویدیو"


#: Allowed extensions per kind, from V_1.0's file dialogs (utils.py:1640-1666).
#: `xlsx` is added to the document list: V_1.0 offered xlsm/xlsb/xls/xltx but
#: not plain .xlsx, which is almost certainly an oversight.
FILE_EXTENSIONS = {
    FileKind.PICTURE: {"png", "jpg", "jpeg", "gif", "webp"},
    FileKind.DOCUMENT: {"docx", "pptx", "xlsx", "xlsm", "xlsb", "xls", "xltx", "pdf", "txt", "csv"},
    FileKind.VIDEO: {"mp4", "mov", "webm"},
}
