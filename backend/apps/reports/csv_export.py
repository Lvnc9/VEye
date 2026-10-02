"""CSV responses for the reports surface (Phase 17) — stdlib `csv`, no new dependency.

Two things every export here gets right, because a spreadsheet is the whole point:

* **A UTF-8 BOM first.** Excel opens a BOM-less UTF-8 file as the machine's ANSI code page, and Persian
  becomes mojibake; the BOM is how it learns the encoding. Other tools ignore it.
* **No formula injection.** Titles, names and notes are typed by people; a cell starting with `=`,
  `+`, `-` or `@` is run as a formula by Excel and LibreOffice. Such a cell is prefixed with `'`
  (OWASP's advice): it stays readable, with a visible leading apostrophe, and can no longer execute.

The response streams row by row (`StreamingHttpResponse`, the technique `pdfgen/bulk.py` uses for the
ZIP) so a long list is never held in memory twice.
"""
import csv

from django.http import StreamingHttpResponse
from django.utils import timezone

BOM = "﻿"
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value):
    """A cell value for the file: `None` is empty, numbers stay numbers, and text that a spreadsheet
    would execute is defused."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "بله" if value else "خیر"
    if isinstance(value, (int, float)):
        return value
    text = str(value)
    return "'" + text if text.startswith(_FORMULA_PREFIXES) else text


class _Echo:
    """A file-like whose `write` returns what it is given, so `csv.writer` can feed a generator."""

    def write(self, value):
        return value


def csv_response(basename: str, header, rows) -> StreamingHttpResponse:
    """`rows` is any iterable of sequences; the file is named `<basename>-YYYYMMDD.csv` (ASCII, so
    every browser keeps the name)."""
    writer = csv.writer(_Echo())

    def stream():
        yield BOM
        yield writer.writerow(header)
        for row in rows:
            yield writer.writerow([safe_cell(cell) for cell in row])

    response = StreamingHttpResponse(stream(), content_type="text/csv; charset=utf-8")
    stamp = timezone.localdate().strftime("%Y%m%d")
    response["Content-Disposition"] = f'attachment; filename="{basename}-{stamp}.csv"'
    response["Cache-Control"] = "no-store"
    return response
