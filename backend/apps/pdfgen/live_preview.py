"""The designer's live paper (Phase 12): a document's pages as images, drawn from
its *unsaved* edits by the same renderers that print it.

Nothing is stored. The edits are written inside a transaction that is always
rolled back, so the real pipeline runs unchanged — content.save_content, the
adapters, render.render and both renderers — and the database never keeps them
(nor do `on_commit` hooks such as file deletion ever run). Only then, outside
the transaction and its row lock, are the pages rasterised with PDFium.

A page is identified by a hash of its bitmap; the client sends the hashes it
already shows and gets images only for the pages that changed.
"""
from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from io import BytesIO

import pypdfium2 as pdfium
from django.db import transaction

from apps.documents import content

from . import render

#: 1.6 × 72 dpi ≈ 115 dpi: an A4 page is about 950 × 1350 px — sharp on screen, small on the wire.
SCALE = 1.6
MAX_PAGES = 20
#: Quantised PNG: text and rules stay crisp, a page is ~15-30 KB instead of ~150 KB.
COLOURS = 64


class _Rollback(Exception):
    def __init__(self, pdf: bytes):
        super().__init__()
        self.pdf = pdf


def render_unsaved(*, user, document_id: int, data: dict) -> bytes:
    """The PDF the document would print with `data` (validated content input)
    saved — without saving it. Raises what save_content raises (a version
    conflict, a locked document), exactly as a real save would."""
    try:
        with transaction.atomic():
            content.save_content(user=user, document_id=document_id, data=data)
            raise _Rollback(render.render(document_id, preview=False))
    except _Rollback as rollback:
        return rollback.pdf


def render_stored(document_id: int) -> bytes:
    return render.render(document_id, preview=False)


@dataclass(frozen=True)
class Pages:
    pages: list[dict]
    page_count: int

    @property
    def truncated(self) -> bool:
        return self.page_count > len(self.pages)


def rasterise(pdf: bytes, known: set[str]) -> Pages:
    """[{hash, image?}] for the first MAX_PAGES pages; `image` (a PNG data URL)
    only when the client does not already hold that hash."""
    pages = []
    document = pdfium.PdfDocument(pdf)
    try:
        count = len(document)
        for index in range(min(count, MAX_PAGES)):
            page = document[index]
            try:
                image = page.render(scale=SCALE).to_pil()
            finally:
                page.close()
            digest = hashlib.sha256(image.tobytes()).hexdigest()[:24]
            entry = {"hash": digest}
            if digest not in known:
                buffer = BytesIO()
                image.convert("RGB").quantize(colors=COLOURS).save(buffer, format="PNG")
                entry["image"] = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
            pages.append(entry)
    finally:
        document.close()
    return Pages(pages=pages, page_count=count)
