import os
import tempfile
from pathlib import Path

from django.conf import settings

from apps.documents.models import Document

from .models import PdfKind


def relative_path(document: Document, kind: str) -> str:
    """Where a document's PDF lives under MEDIA_ROOT. Built only from ids and the
    generated code — nothing user-supplied ever reaches a path."""
    if kind == PdfKind.OFFICIAL:
        return f"pdfs/{document.pk}/{document.full_code}.pdf"
    return f"pdf_previews/{document.pk}.pdf"


def absolute_path(relative: str) -> Path:
    root = Path(settings.MEDIA_ROOT).resolve()
    path = (root / relative).resolve()
    if root not in path.parents:
        raise ValueError("PDF path escapes MEDIA_ROOT")
    return path


def write_atomic(relative: str, data: bytes) -> None:
    """Write `data` so a concurrent download sees either the old file or the new
    one, never a torn one: write a temp file in the same directory, fsync, then
    rename over the target (atomic on POSIX). Creates the directory, so a fresh,
    empty media volume needs no setup."""
    target = absolute_path(relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=target.parent, prefix=".build-", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as temp:
            temp.write(data)
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_name, target)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise
