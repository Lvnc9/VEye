"""چاپ لیست — bulk download of *already built* official PDFs (Phase 6).

Decided with the user: a ZIP of the PDFs that exist, for the selected rows or for the
current register filter. It **never renders** (PDFs are built only by an explicit
action) — documents without a built PDF are listed as missing, with the reason, so the
person can build them and come back. V_1.0 had no such feature.
"""
import re
import tempfile
import zipfile
from dataclasses import dataclass, field

from django.conf import settings
from rest_framework.exceptions import ValidationError

from apps.core.constants import DocumentStatus
from apps.documents import queries
from apps.documents.models import Document

from . import storage
from .models import PdfBuild, PdfKind, PdfStatus

#: `?ids=` may carry more than the cap (the plan trims it); this only bounds the URL.
MAX_IDS_PARAM = 1000

MISSING_REASONS = {
    "not_finalized": "هنوز نهایی نشده است",
    "not_built": "PDF ساخته نشده است",
    "building": "PDF در حال ساخت است",
    "failed": "ساخت PDF ناموفق بود",
    "file_missing": "فایل PDF روی سرور یافت نشد",
}

_UNSAFE_IN_NAME = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


@dataclass
class Plan:
    total: int = 0                      # documents in the selection (before the cap)
    cap: int = 0
    truncated: bool = False
    ready: list = field(default_factory=list)    # [(document, absolute Path)]
    missing: list = field(default_factory=list)  # [{id, full_code, title, reason, reason_label}]


def parse_ids(raw: str) -> list[int]:
    parts = [p for p in (raw or "").replace("،", ",").split(",") if p.strip()]
    if len(parts) > MAX_IDS_PARAM:
        raise ValidationError({"ids": ["تعداد مستندات انتخاب‌شده بیش از حد مجاز است."]})
    try:
        ids = [int(p) for p in parts]
    except ValueError:
        raise ValidationError({"ids": ["شناسهٔ مستندات نامعتبر است."]})
    return list(dict.fromkeys(ids))  # de-duplicated, order kept


def selection(params):
    """The documents a request asks for: the explicit `ids`, else the register's
    current filters (`search` / `group` / `category` / `status`; none = everything)."""
    queryset = Document.objects.all()
    ids = parse_ids(params.get("ids", ""))
    if ids:
        queryset = queryset.filter(pk__in=ids)
    else:
        queryset = queries.apply_filters(queryset, params)
    return queryset.annotate(family_prefix=queries.prefix_expression()).order_by(
        "family_prefix", "number", "revision"
    )


def _missing(document, reason):
    return {
        "id": document.pk,
        "full_code": document.full_code,
        "title": document.title,
        "reason": reason,
        "reason_label": MISSING_REASONS[reason],
    }


def make_plan(queryset) -> Plan:
    cap = settings.BULK_PRINT_MAX_FILES
    plan = Plan(total=queryset.count(), cap=cap)
    plan.truncated = plan.total > cap
    documents = list(queryset[:cap])

    # One query for every document's issued-PDF row; no per-document lookups.
    builds = {
        build.document_id: build
        for build in PdfBuild.objects.filter(document__in=[d.pk for d in documents], kind=PdfKind.OFFICIAL)
    }
    for document in documents:
        build = builds.get(document.pk)
        if build is not None and build.has_file:
            # Present even while a rebuild runs or after a failed rebuild: the previous
            # file is still the issued one (Phase 4 semantics).
            try:
                path = storage.absolute_path(build.path)
            except ValueError:
                path = None
            if path is not None and path.is_file():
                plan.ready.append((document, path))
            else:
                plan.missing.append(_missing(document, "file_missing"))
        elif document.status not in (DocumentStatus.UNDER_CONTROL, DocumentStatus.OBSOLETE):
            plan.missing.append(_missing(document, "not_finalized"))
        elif build is None:
            plan.missing.append(_missing(document, "not_built"))
        elif build.status == PdfStatus.BUILDING:
            plan.missing.append(_missing(document, "building"))
        else:
            plan.missing.append(_missing(document, "failed"))
    return plan


def archive_name(document, taken: set[str]) -> str:
    """`<title>-<code>.pdf` (V_1.0's naming), safe inside a ZIP and unique."""
    title = _UNSAFE_IN_NAME.sub("_", document.title).strip(" .") or "document"
    base = f"{title}-{document.full_code}"
    name, n = f"{base}.pdf", 2
    while name in taken:
        name, n = f"{base} ({n}).pdf", n + 1
    taken.add(name)
    return name


def build_zip(plan: Plan):
    """A ZIP of the plan's ready PDFs, as a rewound temporary file. PDFs are already
    compressed, so entries are stored, not deflated."""
    archive = tempfile.TemporaryFile()
    taken: set[str] = set()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_STORED) as bundle:
        for document, path in plan.ready:
            bundle.write(path, archive_name(document, taken))
    archive.seek(0)
    return archive
