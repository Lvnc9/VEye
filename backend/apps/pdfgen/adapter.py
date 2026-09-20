"""Document (Postgres) -> `PdfInput`: the data-gathering half of V_1.0's Provider
(`extract_from_json` plus the first half of `deliver_to_pdf`,
deliver_convert.py:54-136 and 138-200).

V_1.0 read a JSON file per document, fetched the previous revision's JSON and
every image over HTTP (unguarded — no timeout, no status check) and cached them
in ./img and ./check. Here everything is a database read or a read from local
media storage, and a missing or unreadable image degrades to the renderer's
placeholder instead of crashing the build.
"""
import logging
from io import BytesIO

import jdatetime
from django.db.models import Prefetch
from django.utils import timezone
from PIL import Image

from apps.core.constants import (
    RESPONSIBILITY_ROW_LABELS,
    DocumentStatus,
    SectionType,
    SignOffRole,
    ValidationMark,
)
from apps.documents.models import Document, Section

from . import provider
from .qr import qr_png, verify_url

logger = logging.getLogger("veye")


def jalali(day) -> str:
    """`1404/01/19` — V_1.0's `jdatetime...strftime("%Y/%m/%d")`."""
    return jdatetime.date.fromgregorian(date=day).strftime("%Y/%m/%d")


def _lines(text: str) -> str:
    # A browser <textarea> submits CRLF; V_1.0 (Tkinter) only ever produced "\n",
    # and the renderer splits on "\n" alone, so a stray "\r" would be drawn.
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def _read_png(field, *, flatten: bool = False) -> bytes | None:
    """Bytes of an image field, or None if it is unset, missing, or not a
    readable image (which would otherwise abort the whole build inside
    ReportLab). None makes the renderer draw its placeholder / leave the cell
    empty, as V_1.0 did for a missing file.

    `flatten` composites transparency onto white. The renderer draws signatures
    without a mask (unlike the logo and QR codes), so a transparent PNG signature
    would print as a black box; V_1.0's archived signatures were opaque, which is
    why it never showed. Opaque images pass through untouched."""
    if not field:
        return None
    try:
        with field.open("rb") as handle:
            data = handle.read()
        image = Image.open(BytesIO(data))
        image.verify()
        if flatten:
            image = Image.open(BytesIO(data))
            if image.mode in ("RGBA", "LA", "P") and (
                image.mode != "P" or "transparency" in image.info
            ):
                rgba = image.convert("RGBA")
                background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                out = BytesIO()
                Image.alpha_composite(background, rgba).convert("RGB").save(out, format="PNG")
                data = out.getvalue()
    except (OSError, ValueError, SyntaxError):
        logger.warning("PDF: image %r is missing or unreadable; drawing a placeholder", field.name)
        return None
    return data


def _validation_mark(status: str) -> str:
    """Printed in the control table's merged «وضعیت کنترل» cell. V_1.0 wrote the
    literal 'معتبر' when a document was signed off and replaced it when a newer
    revision superseded it. A document that has not reached control has no
    validity yet, so the cell stays empty rather than claiming one."""
    if status == DocumentStatus.UNDER_CONTROL:
        return ValidationMark.VALID.label
    if status == DocumentStatus.OBSOLETE:
        return ValidationMark.OBSOLETE.label
    return ""


def _signature(signoff) -> provider.SignatureBlock:
    if signoff is None:
        return provider.SignatureBlock()
    return provider.SignatureBlock(
        name=signoff.name,
        position=signoff.position,
        image=_read_png(signoff.signature, flatten=True),
    )


def _long_text(content: dict) -> str:
    """Heading, then the body, then any extra boxes as further paragraphs.

    V_1.0 printed only heading + body (deliver_convert.py:119) even though the
    designer collected extra boxes; the product owner chose to print them.
    Extra boxes are joined to the body by a blank line so each reads as its own
    paragraph, and the result goes through the same `add_body_text` path — so
    the first body line keeps its indent and rich-text markers still work."""
    body = _lines(content.get("body", ""))
    boxes = [_lines(box) for box in content.get("extra_boxes", []) if box and box.strip()]
    if boxes:
        # An empty body doesn't leave a blank paragraph ahead of the first box.
        body = "\n\n".join(([body] if body.strip() else []) + boxes)
    return _lines(content.get("heading", "")) + "\n" + body


def _responsibilities(section: Section) -> list:
    """[[label line, text], ...] — V_1.0's `all_documents['Responsibilities']`.

    The four role rows print «الف:  سمت: … ناظر: …»; any further rows are
    description-only notes printed under «توضیحات: »."""
    rows = []
    for index, row in enumerate(section.responsibility_rows.all()):
        if row.role and index < len(RESPONSIBILITY_ROW_LABELS):
            label = f"{RESPONSIBILITY_ROW_LABELS[index]}:  "
            key = label + f"سمت: {row.post}    ناظر: {row.supervisor}"
        else:
            key = "توضیحات: "
        rows.append([key, _lines(row.text)])
    return rows


def load(document_id: int) -> provider.PdfInput:
    document = (
        Document.objects.prefetch_related(
            "signoffs",
            Prefetch(
                "sections",
                queryset=Section.objects.order_by("position", "id").prefetch_related(
                    "responsibility_rows",
                    "change_rows",
                    "attachment_items__target",
                ),
            ),
        )
        .get(pk=document_id)
    )

    # Number the change table across the whole revision chain: earlier
    # revisions' frozen rows first, then this revision's own.
    number = 0
    previous_changes = []
    for row in document.previous_change_rows():
        number += 1
        previous_changes.append([str(number), jalali(row.date), row.text])

    blocks = []
    for section in document.sections.all():
        kind = section.type
        if kind == SectionType.SHORT_EXPLANATION:
            lines = [line for line in section.content.get("lines", []) if line != ""]
            blocks.append((provider.TEXT, "".join(_lines(line) + "\n" for line in lines)))
        elif kind == SectionType.LONG_EXPLANATION:
            blocks.append((provider.TEXT, _long_text(section.content)))
        elif kind == SectionType.RESPONSIBILITIES:
            blocks.append((provider.RESPONSIBILITIES, _responsibilities(section)))
        elif kind == SectionType.CHANGES_TABLE:
            rows = []
            for row in section.change_rows.all():
                number += 1
                rows.append([str(number), jalali(row.date), row.text])
            blocks.append((provider.TABLE, rows))
        elif kind == SectionType.ATTACHMENT:
            blocks.append(
                (
                    provider.ATTACHMENTS,
                    [
                        [item.caption, item.target.full_code, qr_png(verify_url(item.target))]
                        for item in section.attachment_items.all()
                    ],
                )
            )

    signoffs = {signoff.role: signoff for signoff in document.signoffs.all()}
    saved_at = document.content_saved_at
    day = timezone.localtime(saved_at).date() if saved_at else timezone.localdate()

    # The renderer draws only a PNG logo (V_1.0: `".png" in path`; anything else
    # became a black box). Logos are normalised to PNG on upload; this guards data
    # that arrived some other way.
    logo = _read_png(document.logo) if document.logo.name.lower().endswith(".png") else None

    return provider.PdfInput(
        title=document.title,
        whole_code=document.full_code,
        review=document.revision_display,
        date=jalali(day),
        validation=_validation_mark(document.status),
        upper_footnote=document.footnote1,
        lower_footnote=document.footnote2,
        logo=logo,
        qr=qr_png(verify_url(document)),
        creater=_signature(signoffs.get(SignOffRole.CREATER)),
        confirmer=_signature(signoffs.get(SignOffRole.CONFIRMER)),
        approver=_signature(signoffs.get(SignOffRole.APPROVER)),
        previous_changes=tuple(previous_changes),
        blocks=tuple(blocks),
    )
