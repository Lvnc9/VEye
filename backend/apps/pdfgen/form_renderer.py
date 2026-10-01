"""The compact form PDF (Phase 11, ADR-011).

A فرم is a controlled blank to be printed and filled in by hand. Unlike the
owner's renderer (`renderer.py`, which gives page 1 to a big header and the
control table), the form starts on page 1, and every page carries the form's
identity so a loose sheet is still identifiable:

* a header band — logo, title, company name / subtitle, and a column with the
  code, revision, date and «صفحه X از Y»;
* a footer — the two footnotes and the QR code of the verify page;
* on a preview, the «پیش نمایش» watermark; on a superseded revision, «منسوخ» on every page;
* at the foot of the last page, once, the approval strip (تهیه / تایید / تصویب کننده).

It is built with ReportLab platypus: each element becomes a flowable, and the
page furniture is drawn by a canvas that waits for the last page so it knows
the page count. Everything is a pure function of `FormPdfInput`: no globals, a
new document and canvas per call, so builds can run side by side.

Layout constants are millimetres and are mirrored by the designer's A4 canvas
(frontend/lib/form-layout.ts) so the two look alike.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO

from django.conf import settings
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Flowable,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Spacer,
    Table,
    TableStyle,
)

from . import rtl

# --- page geometry (mm) ---------------------------------------------------
MARGIN_SIDE = 12
MARGIN_TOP = 10
MARGIN_BOTTOM = 8
HEADER_HEIGHT = 24
HEADER_GAP = 4
FOOTER_HEIGHT = 16
FOOTER_GAP = 3
LOGO_CELL = 26
META_CELL = 46

LINE_COLOR = (0.2, 0.2, 0.2)
MUTED = (0.42, 0.45, 0.51)  # #6c7482, the owner's footer grey
BAND_FILL = (0.9, 0.91, 0.93)
LEADING = 1.55
# Input elements (mm)
PHOTO_WIDTH = 30
PHOTO_HEIGHT = 40
PHOTO_GAP = 4
ANSWER_LINE = 8
SIGNATURE_GAP = 3

PREVIEW_TEXT = "پیش نمایش"
OBSOLETE_TEXT = "منسوخ"


@dataclass(frozen=True)
class Signer:
    role_label: str
    name: str = ""
    position: str = ""
    #: Kept for whoever reads the data; the strip no longer prints it (2026-09-30).
    date: str = ""
    image: bytes | None = None


@dataclass(frozen=True)
class FormPdfInput:
    title: str
    full_code: str
    revision: str
    date: str
    #: A superseded revision: «منسوخ» is drawn behind every page (2026-09-30; it replaced the
    #: header's «وضعیت: معتبر» row).
    obsolete: bool = False
    company_name: str = ""
    subtitle: str = ""
    show_letter_box: bool = False
    footnote1: str = ""
    footnote2: str = ""
    logo: bytes | None = None
    qr: bytes | None = None
    orientation: str = "portrait"
    base_font_size: int = 10
    approval_strip: bool = True
    signers: tuple[Signer, ...] = ()
    #: The stored elements (form_schema's normalised dicts), in page order.
    elements: tuple[dict, ...] = field(default_factory=tuple)


def _fonts(size: float) -> rtl.Font:
    name = settings.PDF_FONT_NAME
    return rtl.Font(regular=name, bold=f"{name}-Bold", size=size)


# --------------------------------------------------------------------------
# Flowables
# --------------------------------------------------------------------------


class RTLParagraph(Flowable):
    """Wrapped right-to-left text with inline markers; splits across pages by
    line. `boxed` draws a frame around it (a callout)."""

    def __init__(self, text: str, font: rtl.Font, *, align="right", bold=False, color=(0, 0, 0), boxed=False, _lines=None):
        super().__init__()
        self.text = text
        self.font = font
        self.align = align
        self.bold = bold
        self.color = color
        self.boxed = boxed
        self.pad = 3 * mm if boxed else 0
        self.leading = font.size * LEADING
        self._lines = _lines

    def wrap(self, avail_width, avail_height):
        self.width = avail_width
        inner = avail_width - 2 * self.pad
        if self._lines is None:
            self._lines = rtl.wrap(self.text, self.font, inner, bold=self.bold)
        self.height = len(self._lines) * self.leading + 2 * self.pad
        return self.width, self.height

    def split(self, avail_width, avail_height):
        self.wrap(avail_width, avail_height)
        fits = int((avail_height - 2 * self.pad) // self.leading)
        if fits <= 0 or fits >= len(self._lines):
            return []
        make = lambda lines: RTLParagraph(  # noqa: E731
            self.text, self.font, align=self.align, bold=self.bold, color=self.color, boxed=self.boxed, _lines=lines
        )
        return [make(self._lines[:fits]), make(self._lines[fits:])]

    def draw(self):
        c = self.canv
        if self.boxed:
            c.saveState()
            c.setStrokeColorRGB(*LINE_COLOR)
            c.setLineWidth(0.6)
            c.rect(0, 0, self.width, self.height)
            c.restoreState()
        c.setFillColorRGB(*self.color)
        right = self.width - self.pad
        inner = self.width - 2 * self.pad
        # Baseline of the first line: one leading down, lifted by the descent.
        y = self.height - self.pad - self.leading + (self.leading - self.font.size) / 2 + self.font.size * 0.2
        for line in self._lines:
            width = rtl.line_width(line, self.font)
            if self.align == "center":
                x_right = right - (inner - width) / 2
            elif self.align == "left":
                x_right = self.pad + width
            else:
                x_right = right
            rtl.draw_line(c, line, self.font, x_right=x_right, y=y)
            y -= self.leading


class Heading(Flowable):
    """A section headline: a shaded band, an underlined title, or plain bold."""

    SIZES = {1: 2.5, 2: 1.5, 3: 0.5}  # points above the base size

    def __init__(self, text: str, base_size: int, *, style: str, level: int, align: str):
        super().__init__()
        self.style = style
        self.pad = 1.8 * mm if style == "band" else 0.6 * mm
        self.paragraph = RTLParagraph(text, _fonts(base_size + self.SIZES[level]), align=align, bold=True)
        self.space_before = 2 * mm
        self.space_after = 1.5 * mm

    def wrap(self, avail_width, avail_height):
        self.width = avail_width
        pad_x = 2 * mm if self.style == "band" else 0
        _, h = self.paragraph.wrap(avail_width - 2 * pad_x, avail_height)
        self.pad_x = pad_x
        self.height = h + 2 * self.pad + self.space_before + self.space_after
        return self.width, self.height

    def draw(self):
        c = self.canv
        body = self.height - self.space_before - self.space_after
        bottom = self.space_after
        if self.style == "band":
            c.saveState()
            c.setFillColorRGB(*BAND_FILL)
            c.setStrokeColorRGB(*LINE_COLOR)
            c.setLineWidth(0.6)
            c.rect(0, bottom, self.width, body, fill=1, stroke=1)
            c.restoreState()
        elif self.style == "underline":
            c.saveState()
            c.setStrokeColorRGB(*LINE_COLOR)
            c.setLineWidth(0.9)
            c.line(0, bottom, self.width, bottom)
            c.restoreState()
        self.paragraph.drawOn(c, self.pad_x, bottom + self.pad)


class Rule(Flowable):
    """A separation line across the frame."""

    DASHES = {"solid": None, "dashed": (4, 2.5), "dotted": (0.8, 1.8), "double": None}

    def __init__(self, *, style: str, thickness: float, space_before: float, space_after: float):
        super().__init__()
        self.style = style
        self.thickness = thickness
        self.before = space_before * mm
        self.after = space_after * mm
        self.gap = 1.6 if style == "double" else 0

    def wrap(self, avail_width, avail_height):
        self.width = avail_width
        self.height = self.before + self.after + self.thickness * (2 if self.gap else 1) + self.gap
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.saveState()
        c.setStrokeColorRGB(*LINE_COLOR)
        c.setLineWidth(self.thickness)
        dash = self.DASHES[self.style]
        if dash:
            c.setDash(*dash)
        y = self.after + self.thickness / 2
        c.line(0, y, self.width, y)
        if self.gap:
            y += self.thickness + self.gap
            c.line(0, y, self.width, y)
        c.restoreState()


class LetterBox(Flowable):
    """«شماره / تاریخ / پیوست» at the top of the first page, on the left — the
    blanks a Persian letterhead leaves for the secretariat."""

    LABELS = ("شماره:", "تاریخ:", "پیوست:")

    def __init__(self, base_size: int):
        super().__init__()
        self.font = _fonts(base_size - 1)
        self.line_height = self.font.size * 1.9

    def wrap(self, avail_width, avail_height):
        self.width = avail_width
        self.height = self.line_height * len(self.LABELS) + 1 * mm
        return self.width, self.height

    def draw(self):
        c = self.canv
        blank = 30 * mm
        y = self.height - self.line_height + 2
        for label in self.LABELS:
            label_width = self.font.width(label)
            rtl.draw_line(c, [(label, rtl.NORMAL)], self.font, x_right=blank + label_width + 1.5 * mm, y=y)
            c.saveState()
            c.setStrokeColorRGB(*MUTED)
            c.setLineWidth(0.5)
            c.setDash(0.8, 1.6)
            c.line(0, y - 1.5, blank, y - 1.5)
            c.restoreState()
            y -= self.line_height


def _blank_line(c, x0, x1, y, style):
    """The line a hand fills in. `style`: underline, dotted or box."""
    c.saveState()
    c.setStrokeColorRGB(*LINE_COLOR)
    c.setLineWidth(0.5)
    if style == "dotted":
        c.setDash(0.8, 1.6)
    if style == "box":
        c.rect(x0, y - 1.6 * mm, x1 - x0, 5.6 * mm)
    else:
        c.line(x0, y - 1, x1, y - 1)
    c.restoreState()


def _digit_boxes(c, x_right, x_min, y, count):
    """`count` boxes for digits, right after the label; left-to-right digits, so
    the first box is the leftmost of the run."""
    size = min(5 * mm, max(2.5 * mm, (x_right - x_min) / count))
    c.saveState()
    c.setStrokeColorRGB(*LINE_COLOR)
    c.setLineWidth(0.5)
    left = x_right - size * count
    for i in range(count):
        c.rect(left + i * size, y - 1.4 * mm, size, size)
    c.restoreState()


class FieldGrid(Flowable):
    """Rows of labelled blanks, right to left, with an optional 3×4 photo box on
    the left. Splits between rows; the photo stays with the first rows."""

    def __init__(self, element: dict, base_size: int, *, rows=None, photo=None):
        super().__init__()
        self.element = element
        self.font = _fonts(base_size)
        self.rows = element["rows"] if rows is None else rows
        self.photo = element["photo"] if photo is None else photo
        self.row_height = element["row_height"] * mm
        self.gap_after = 1.5 * mm

    def _min_height(self, rows) -> float:
        photo = PHOTO_HEIGHT * mm + 1 * mm if self.photo else 0
        return max(len(rows) * self.row_height, photo) + self.gap_after

    def wrap(self, avail_width, avail_height):
        self.width = avail_width
        self.height = self._min_height(self.rows)
        return self.width, self.height

    def split(self, avail_width, avail_height):
        fits = int((avail_height - self.gap_after) // self.row_height)
        if fits <= 0 or fits >= len(self.rows):
            return []
        if self.photo and fits * self.row_height < PHOTO_HEIGHT * mm + 1 * mm:
            return []
        return [
            FieldGrid(self.element, self.font.size, rows=self.rows[:fits], photo=self.photo),
            FieldGrid(self.element, self.font.size, rows=self.rows[fits:], photo=False),
        ]

    def draw(self):
        c = self.canv
        top = self.height
        left_edge = (PHOTO_WIDTH + PHOTO_GAP) * mm if self.photo else 0
        area = self.width - left_edge
        blank = self.element["blank"]

        for index, row in enumerate(self.rows):
            baseline = top - (index + 1) * self.row_height + self.row_height * 0.32
            x_right = self.width
            for cell in row["cells"]:
                cell_width = area * cell["width"] / 100
                x_left = x_right - cell_width
                self._cell(c, cell, x_left + 1.5 * mm, x_right - 1 * mm, baseline, blank)
                x_right = x_left

        if self.photo:
            c.saveState()
            c.setStrokeColorRGB(*LINE_COLOR)
            c.setLineWidth(0.6)
            box_top = top - 0.5 * mm
            c.rect(0, box_top - PHOTO_HEIGHT * mm, PHOTO_WIDTH * mm, PHOTO_HEIGHT * mm)
            c.setFillColorRGB(*MUTED)
            small = _fonts(self.font.size - 2)
            middle = box_top - PHOTO_HEIGHT * mm / 2
            _draw_text(c, "محل الصاق عکس", small, x_right=0, y=middle + 1 * mm, center_in=(0, PHOTO_WIDTH * mm))
            # Vazir has no «×» glyph, so the size is written out.
            _draw_text(c, "ابعاد ۳ در ۴", small, x_right=0, y=middle - 3.5 * mm, center_in=(0, PHOTO_WIDTH * mm))
            c.restoreState()

    def _cell(self, c, cell, x_min, x_right, baseline, blank):
        label = cell["label"].strip()
        c.setFillColorRGB(0, 0, 0)
        if cell["type"] == "checkbox":
            size = 3.4 * mm
            c.saveState()
            c.setStrokeColorRGB(*LINE_COLOR)
            c.setLineWidth(0.6)
            c.rect(x_right - size, baseline - 0.6 * mm, size, size)
            c.restoreState()
            if label:
                rtl.draw_line(c, [(label, rtl.NORMAL)], self.font, x_right=x_right - size - 1.5 * mm, y=baseline)
            return

        text = f"{label}:" if label else ""
        line = [(text, rtl.NORMAL)]
        label_width = rtl.line_width(line, self.font) if text else 0
        if text:
            rtl.draw_line(c, line, self.font, x_right=x_right, y=baseline)
        blank_right = x_right - label_width - (1.5 * mm if text else 0)
        if blank_right - x_min < 3 * mm:
            return  # the label fills the cell

        if cell["type"] == "national_code":
            _digit_boxes(c, blank_right, x_min, baseline, 10)
        elif cell["type"] == "phone":
            _digit_boxes(c, blank_right, x_min, baseline, 11)
        elif cell["type"] == "date":
            # «....../....../......», written year/month/day left to right.
            third = (blank_right - x_min - 4 * mm) / 3
            x = x_min
            for part in range(3):
                _blank_line(c, x, x + third, baseline, "dotted" if blank == "box" else blank)
                x += third
                if part < 2:
                    c.setFont(self.font.regular, self.font.size)
                    c.drawCentredString(x + 1 * mm, baseline, "/")
                    x += 2 * mm
        else:
            _blank_line(c, x_min, blank_right, baseline, blank)


class AnswerBox(Flowable):
    """Room to write an answer: a title, then ruled lines or an empty frame."""

    def __init__(self, element: dict, base_size: int, max_height: float):
        super().__init__()
        self.element = element
        self.font = _fonts(base_size)
        self.title_height = self.font.size * LEADING if element["label"].strip() else 0
        lines = element["lines"]
        box = (lines * ANSWER_LINE + 2) * mm if lines else element["height"] * mm
        # Never taller than a page's frame: platypus cannot place it otherwise.
        self.box_height = min(box, max_height - self.title_height - 3 * mm)
        self.gap_after = 2 * mm

    def wrap(self, avail_width, avail_height):
        self.width = avail_width
        self.height = self.title_height + self.box_height + self.gap_after
        return self.width, self.height

    def draw(self):
        c = self.canv
        top = self.height
        if self.title_height:
            c.setFillColorRGB(0, 0, 0)
            baseline = top - self.title_height + (self.title_height - self.font.size) / 2 + self.font.size * 0.2
            rtl.draw_line(c, [(self.element["label"], rtl.BOLD)], self.font, x_right=self.width, y=baseline)
        box_top = top - self.title_height
        bottom = box_top - self.box_height
        c.saveState()
        c.setStrokeColorRGB(*LINE_COLOR)
        if self.element["framed"]:
            c.setLineWidth(0.6)
            c.rect(0, bottom, self.width, self.box_height)
        c.setLineWidth(0.4)
        if self.element["line_style"] == "dotted":
            c.setDash(0.8, 1.8)
        inset = 3 * mm if self.element["framed"] else 0
        y = box_top - ANSWER_LINE * mm
        for _ in range(self.element["lines"]):
            if y <= bottom + 1:
                break
            c.line(inset, y, self.width - inset, y)
            y -= ANSWER_LINE * mm
        c.restoreState()


class SignatureRow(Flowable):
    """Signature boxes side by side, the first on the right, then the stamp."""

    def __init__(self, element: dict, base_size: int):
        super().__init__()
        self.element = element
        self.font = _fonts(base_size - 1)
        self.boxes = list(element["boxes"]) + (
            [{"caption": "محل مهر", "name_line": False, "date_line": False}] if element["stamp"] else []
        )
        self.gap_before = 3 * mm
        self.gap_after = 2 * mm

    def wrap(self, avail_width, avail_height):
        self.width = avail_width
        self.height = self.element["height"] * mm + self.gap_before + self.gap_after
        return self.width, self.height

    def draw(self):
        c = self.canv
        count = len(self.boxes)
        box_width = (self.width - SIGNATURE_GAP * mm * (count - 1)) / count
        box_height = self.element["height"] * mm
        bottom = self.gap_after
        top = bottom + box_height
        x_right = self.width
        for box in self.boxes:
            x_left = x_right - box_width
            c.saveState()
            c.setStrokeColorRGB(*LINE_COLOR)
            c.setLineWidth(0.6)
            c.rect(x_left, bottom, box_width, box_height)
            c.restoreState()
            c.setFillColorRGB(0, 0, 0)
            y = top - 5 * mm
            if box["caption"].strip():
                _draw_text(c, box["caption"], self.font, x_right=0, y=y, bold=True, center_in=(x_left, x_right))
            for wanted, label in ((box["name_line"], "نام و نام خانوادگی:"), (box["date_line"], "تاریخ:")):
                if not wanted:
                    continue
                y -= 6 * mm
                if y < bottom + 2 * mm:
                    break
                line = [(label, rtl.NORMAL)]
                rtl.draw_line(c, line, self.font, x_right=x_right - 2 * mm, y=y)
                _blank_line(c, x_left + 2 * mm, x_right - 3 * mm - rtl.line_width(line, self.font), y, "dotted")
            x_right = x_left - SIGNATURE_GAP * mm


def _mark(c, x, y, size, shape="square"):
    """An empty tick box (or circle) with its bottom-left corner at (x, y)."""
    c.saveState()
    c.setStrokeColorRGB(*LINE_COLOR)
    c.setLineWidth(0.6)
    if shape == "circle":
        c.circle(x + size / 2, y + size / 2, size / 2)
    else:
        c.rect(x, y, size, size)
    c.restoreState()


class CheckCell(Flowable):
    """A tick box (or circle) centred in a table cell."""

    SIZE = 3.4 * mm

    def __init__(self, shape="square"):
        super().__init__()
        self.shape = shape

    def wrap(self, avail_width, avail_height):
        self.width, self.height = avail_width, self.SIZE
        return self.width, self.height

    def draw(self):
        _mark(self.canv, (self.width - self.SIZE) / 2, 0, self.SIZE, self.shape)


class DateCell(Flowable):
    """«/  /» — the slashes of a Jalali date to fill in, centred."""

    def __init__(self, font: rtl.Font):
        super().__init__()
        self.font = font

    def wrap(self, avail_width, avail_height):
        self.width, self.height = avail_width, self.font.size
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.setFillColorRGB(*MUTED)
        c.setFont(self.font.regular, self.font.size)
        step = min(8 * mm, self.width / 3)
        middle = self.width / 2
        c.drawCentredString(middle - step / 2, 1, "/")
        c.drawCentredString(middle + step / 2, 1, "/")


TABLE_PAD_X = 3
TABLE_PAD_Y = 2


def _table_cell(text: str, column: dict, font: rtl.Font, *, header: bool):
    if header:
        return RTLParagraph(text, font, align="center", bold=True) if text.strip() else ""
    if text.strip():
        return RTLParagraph(text, font, align=column["align"])
    return ""


def _table(element, data, numbering):
    columns = element["columns"]
    count = len(columns)
    font = _fonts(element["font_size"] or data.base_font_size - 1)
    header_rows = len(element["header"])

    # Logical grid: header rows, rows written in advance, blank rows.
    body = [list(row) for row in element["rows"]] + [[""] * count for _ in range(element["blank_rows"])]
    grid = []
    for row in element["header"]:
        grid.append([_table_cell(text, column, font, header=True) for text, column in zip(row, columns)])
    for number, row in enumerate(body, start=1):
        cells = []
        for text, column in zip(row, columns):
            if column["type"] == "row_number":
                cells.append(RTLParagraph(text or str(number), font, align="center"))
            elif column["type"] == "checkbox" and not text.strip():
                cells.append(CheckCell())
            elif column["type"] == "date" and not text.strip():
                cells.append(DateCell(font))
            else:
                cells.append(_table_cell(text, column, font, header=False))
        grid.append(cells)

    # A merged range is drawn from its top-left cell in platypus terms, which,
    # with the columns reversed, is the range's *last* logical column. Move the
    # anchor's content there; the covered cells are never drawn.
    for merge in element["merges"]:
        row, first, last = merge["row"], merge["col"], merge["col"] + merge["colspan"] - 1
        anchor = grid[row][first]
        for y in range(row, row + merge["rowspan"]):
            for x in range(first, last + 1):
                grid[y][x] = ""
        grid[row][last] = anchor

    flowables = []
    if element["title"].strip():
        title = RTLParagraph(element["title"], _fonts(data.base_font_size), bold=True)
        title.keepWithNext = True
        flowables += [title, Spacer(1, 1 * mm)]
    flowables.append(_TableFlowable(element, grid, header_rows))
    flowables.append(Spacer(1, 2.5 * mm))
    return flowables


class _TableFlowable(Flowable):
    """Builds the platypus Table once the frame width is known (widths are
    percentages), with column 1 on the right."""

    def __init__(self, element, grid, header_rows):
        super().__init__()
        self.element = element
        self.grid = grid
        self.header_rows = header_rows
        self._table = None

    def _build(self, width):
        element = self.element
        widths = [width * column["width"] / 100 for column in element["columns"]]
        min_body = element["row_height"] * mm
        # Each drawn cell's width, rows and anchor position (merged ranges count once).
        spans = {}
        for merge in element["merges"]:
            last = merge["col"] + merge["colspan"] - 1
            spans[(merge["row"], last)] = (sum(widths[merge["col"]:last + 1]), merge["rowspan"])
        heights, tall = [], []
        for index, row in enumerate(self.grid):
            needed = 0
            for column, cell in enumerate(row):
                if not isinstance(cell, Flowable):
                    continue
                cell_width, rowspan = spans.get((index, column), (widths[column], 1))
                _, h = cell.wrap(cell_width - 2 * TABLE_PAD_X, 10_000)
                if rowspan == 1:
                    needed = max(needed, h)
                else:
                    tall.append((index, rowspan, h + 2 * TABLE_PAD_Y))
            needed += 2 * TABLE_PAD_Y
            heights.append(max(needed, 6 * mm) if index < self.header_rows else max(needed, min_body))
        # A cell spanning rows grows the last of them if they are too short together.
        for index, rowspan, needed in tall:
            short = needed - sum(heights[index:index + rowspan])
            if short > 0:
                heights[index + rowspan - 1] += short
        # Reverse every row and the widths: platypus lays column 0 on the left.
        data = [list(reversed(row)) for row in self.grid]
        table = Table(
            data,
            colWidths=list(reversed(widths)),
            rowHeights=heights,
            repeatRows=self.header_rows if element["repeat_header"] else 0,
        )
        table.setStyle(TableStyle(self._style()))
        return table

    def _style(self):
        element = self.element
        last_header = self.header_rows - 1
        style = [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), TABLE_PAD_X),
            ("RIGHTPADDING", (0, 0), (-1, -1), TABLE_PAD_X),
            ("TOPPADDING", (0, 0), (-1, -1), TABLE_PAD_Y),
            ("BOTTOMPADDING", (0, 0), (-1, -1), TABLE_PAD_Y),
        ]
        if element["header_shade"]:
            style.append(("BACKGROUND", (0, 0), (-1, last_header), BAND_FILL))
        count = len(element["columns"])
        for merge in element["merges"]:
            # Logical columns c..c+n-1 are platypus columns count-c-n .. count-1-c.
            left = count - merge["col"] - merge["colspan"]
            right = count - 1 - merge["col"]
            bottom = merge["row"] + merge["rowspan"] - 1
            style.append(("SPAN", (left, merge["row"]), (right, bottom)))
        borders = element["borders"]
        if borders == "all":
            style.append(("GRID", (0, 0), (-1, -1), 0.5, LINE_COLOR))
        elif borders == "outer":
            style += [("BOX", (0, 0), (-1, -1), 0.8, LINE_COLOR), ("LINEBELOW", (0, last_header), (-1, last_header), 0.6, LINE_COLOR)]
        elif borders == "horizontal":
            style += [("LINEABOVE", (0, 0), (-1, 0), 0.6, LINE_COLOR), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE_COLOR)]
        else:
            style.append(("LINEBELOW", (0, last_header), (-1, last_header), 0.6, LINE_COLOR))
        return style

    def wrap(self, avail_width, avail_height):
        if self._table is None or self._table_width != avail_width:
            self._table = self._build(avail_width)
            self._table_width = avail_width
        return self._table.wrap(avail_width, avail_height)

    def split(self, avail_width, avail_height):
        self.wrap(avail_width, avail_height)
        return self._table.split(avail_width, avail_height)

    def drawOn(self, canvas, x, y, _sW=0):
        self._table.drawOn(canvas, x, y, _sW)

    def draw(self):  # pragma: no cover - drawOn is used
        self._table.draw()


class ChoiceGroup(Flowable):
    """A question answered by ticking: the question on the right, then its
    options right to left — on one flowing line, one per line, or in columns."""

    MARK = 3.2 * mm
    GAP = 1.5 * mm
    SPACING = 6 * mm
    OTHER_BLANK = 30 * mm

    def __init__(self, element: dict, base_size: int):
        super().__init__()
        self.element = element
        self.font = _fonts(base_size)
        self.line_height = self.font.size * 1.9
        self.gap_after = 1.5 * mm
        self.options = [(text, False) for text in element["options"]]
        if element["other"]:
            self.options.append(("سایر:", True))

    def _option_width(self, text, is_other):
        return self.MARK + self.GAP + self.font.width(text) + (self.GAP + self.OTHER_BLANK if is_other else 0)

    def _layout(self, width):
        """[(line, x_right, text, is_other)] for each option, and the line count."""
        label = self.element["label"].strip()
        placed = []
        layout = self.element["layout"]
        if layout == "inline":
            line = 0
            x = width
            if label:
                x -= self.font.width(f"{label}:", rtl.BOLD) + self.SPACING
            for text, is_other in self.options:
                needed = self._option_width(text, is_other)
                if x - needed < 0 and x < width:
                    line, x = line + 1, width
                placed.append((line, x, text, is_other))
                x -= needed + self.SPACING
            return placed, line + 1
        first = 1 if label else 0
        indent = 4 * mm
        if layout == "vertical":
            for index, (text, is_other) in enumerate(self.options):
                placed.append((first + index, width - indent, text, is_other))
            return placed, first + len(self.options)
        columns = self.element["columns"]
        column_width = (width - indent) / columns
        for index, (text, is_other) in enumerate(self.options):
            row, column = divmod(index, columns)
            placed.append((first + row, width - indent - column * column_width, text, is_other))
        rows = -(-len(self.options) // columns)
        return placed, first + rows

    def wrap(self, avail_width, avail_height):
        self.width = avail_width
        self._placed, lines = self._layout(avail_width)
        self.height = lines * self.line_height + self.gap_after
        return self.width, self.height

    def draw(self):
        c = self.canv
        top = self.height
        baseline = lambda line: top - (line + 1) * self.line_height + self.line_height * 0.32  # noqa: E731
        c.setFillColorRGB(0, 0, 0)
        label = self.element["label"].strip()
        if label:
            rtl.draw_line(c, [(f"{label}:", rtl.BOLD)], self.font, x_right=self.width, y=baseline(0))
        for line, x_right, text, is_other in self._placed:
            y = baseline(line)
            _mark(c, x_right - self.MARK, y - 0.6 * mm, self.MARK, self.element["shape"])
            text_right = x_right - self.MARK - self.GAP
            rtl.draw_line(c, [(text, rtl.NORMAL)], self.font, x_right=text_right, y=y)
            if is_other:
                blank_right = text_right - self.font.width(text) - self.GAP
                _blank_line(c, blank_right - self.OTHER_BLANK, blank_right, y, "dotted")


def _matrix_table(element, data):
    font = _fonts(data.base_font_size - 1)
    scale = element["scale"]
    comment = element["comment"]
    item_width = element["item_width"]
    comment_width = 20 if comment else 0
    grade_width = (100 - item_width - comment_width) / len(scale)
    widths = [item_width] + [grade_width] * len(scale) + ([comment_width] if comment else [])

    header = [RTLParagraph(element["item_title"], font, align="center", bold=True)]
    header += [RTLParagraph(grade, font, align="center", bold=True) for grade in scale]
    if comment:
        header.append(RTLParagraph(element["comment_title"], font, align="center", bold=True))
    grid = [header]
    for number, item in enumerate(element["items"], start=1):
        text = f"{number}. {item}" if element["numbered"] else item
        row = [RTLParagraph(text, font)] + [CheckCell(element["shape"]) for _ in scale]
        if comment:
            row.append("")
        grid.append(row)
    return grid, widths


class MatrixFlowable(Flowable):
    """The rating grid, built at the frame's width; the item column on the right."""

    def __init__(self, element, data):
        super().__init__()
        self.grid, self.widths = _matrix_table(element, data)
        self._table = None

    def _build(self, width):
        widths = [width * w / 100 for w in self.widths]
        heights = []
        for index, row in enumerate(self.grid):
            needed = 0
            for cell, column_width in zip(row, widths):
                if isinstance(cell, Flowable):
                    needed = max(needed, cell.wrap(column_width - 2 * TABLE_PAD_X, 10_000)[1])
            heights.append(max(needed + 2 * TABLE_PAD_Y, 7 * mm if index else 6 * mm))
        table = Table([list(reversed(row)) for row in self.grid], colWidths=list(reversed(widths)), rowHeights=heights, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, LINE_COLOR),
                    ("BACKGROUND", (0, 0), (-1, 0), BAND_FILL),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), TABLE_PAD_X),
                    ("RIGHTPADDING", (0, 0), (-1, -1), TABLE_PAD_X),
                    ("TOPPADDING", (0, 0), (-1, -1), TABLE_PAD_Y),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), TABLE_PAD_Y),
                ]
            )
        )
        return table

    def wrap(self, avail_width, avail_height):
        if self._table is None or self._width != avail_width:
            self._table, self._width = self._build(avail_width), avail_width
        return self._table.wrap(avail_width, avail_height)

    def split(self, avail_width, avail_height):
        self.wrap(avail_width, avail_height)
        return self._table.split(avail_width, avail_height)

    def drawOn(self, canvas, x, y, _sW=0):
        self._table.drawOn(canvas, x, y, _sW)

    def draw(self):  # pragma: no cover - drawOn is used
        self._table.draw()


# --------------------------------------------------------------------------
# Elements → flowables
# --------------------------------------------------------------------------


class _Numbering:
    """«1. », «2.1. » for numbered headings, by level.

    The separator is "." and not "-": bidi joins digits across a "." (a common
    separator) but not across a "-" after Persian text, where «2-1» would print
    as «1-2» — the trap frontend/lib/jalali.ts documents for dates."""

    def __init__(self):
        self.counters = [0, 0, 0]

    def next(self, level: int) -> str:
        self.counters[level - 1] += 1
        for deeper in range(level, 3):
            self.counters[deeper] = 0
        return ".".join(str(n) for n in self.counters[:level]) + ". "


def _heading(element, data, numbering):
    text = element["text"]
    if not text.strip():
        return []
    if element["numbered"]:
        text = numbering.next(element["level"]) + text
    return [Heading(text, data.base_font_size, style=element["style"], level=element["level"], align=element["align"])]


def _text(element, data, numbering):
    if not element["text"].strip():
        return []
    size = element["size"] or data.base_font_size
    return [
        RTLParagraph(element["text"], _fonts(size), align=element["align"], boxed=element["boxed"]),
        Spacer(1, 1.5 * mm),
    ]


def _divider(element, data, numbering):
    return [
        Rule(
            style=element["style"],
            thickness=element["thickness"],
            space_before=element["space_before"],
            space_after=element["space_after"],
        )
    ]


def _spacer(element, data, numbering):
    return [Spacer(1, element["height"] * mm)]


def _page_break(element, data, numbering):
    return [PageBreak()]


def _fields(element, data, numbering):
    return [FieldGrid(element, data.base_font_size)]


def _answer_box(element, data, numbering, max_height):
    return [AnswerBox(element, data.base_font_size, max_height)]


def _signatures(element, data, numbering):
    return [SignatureRow(element, data.base_font_size)]


def _choices(element, data, numbering):
    return [ChoiceGroup(element, data.base_font_size)]


def _matrix(element, data, numbering):
    flowables = []
    if element["title"].strip():
        title = RTLParagraph(element["title"], _fonts(data.base_font_size), bold=True)
        title.keepWithNext = True
        flowables += [title, Spacer(1, 1 * mm)]
    return flowables + [MatrixFlowable(element, data), Spacer(1, 2.5 * mm)]


def _questions(element, data, numbering, max_height):
    font = _fonts(data.base_font_size)
    flowables = []
    for number, item in enumerate(element["items"], start=1):
        text = f"{number}. {item['text']}" if element["numbered"] else item["text"]
        block = [RTLParagraph(text, font)]
        answer = item["answer"]
        if answer == "lines":
            block.append(AnswerBox(
                {"label": "", "lines": item["lines"], "height": 0, "line_style": "dotted", "framed": False},
                data.base_font_size, max_height,
            ))
        elif answer == "box":
            block.append(AnswerBox(
                {"label": "", "lines": 0, "height": item["height"], "line_style": "dotted", "framed": True},
                data.base_font_size, max_height - 20 * mm,
            ))
        elif answer == "yes_no":
            block.append(ChoiceGroup(
                {"label": "", "options": ["بله", "خیر"], "shape": "square", "layout": "inline", "columns": 2, "other": False},
                data.base_font_size,
            ))
        # A question is never parted from the room for its answer.
        flowables += [KeepTogether(block), Spacer(1, 1.5 * mm)]
    return flowables


BUILDERS = {
    "heading": _heading,
    "text": _text,
    "divider": _divider,
    "spacer": _spacer,
    "page_break": _page_break,
    "fields": _fields,
    "signatures": _signatures,
    "table": lambda element, data, numbering: _table(element, data, numbering),
    "choices": _choices,
    "matrix": _matrix,
}

#: Builders that need the frame's height (to never exceed a page).
SIZED_BUILDERS = {
    "answer_box": _answer_box,
    "questions": _questions,
}


def _cell(text: str, size: float, *, bold=False, align="center", color=(0, 0, 0)) -> RTLParagraph:
    return RTLParagraph(text, _fonts(size), bold=bold, align=align, color=color)


class _Image(Flowable):
    """A PNG scaled to fit a box, keeping its aspect ratio; centred."""

    def __init__(self, data: bytes, width: float, height: float):
        super().__init__()
        self.reader = ImageReader(BytesIO(data))
        self.box = (width, height)

    def wrap(self, avail_width, avail_height):
        self.width, self.height = min(self.box[0], avail_width), self.box[1]
        return self.width, self.height

    def draw(self):
        iw, ih = self.reader.getSize()
        scale = min(self.width / iw, self.height / ih)
        w, h = iw * scale, ih * scale
        self.canv.drawImage(self.reader, (self.width - w) / 2, (self.height - h) / 2, w, h, mask="auto")


class _SignatureCell(Flowable):
    """«امضا:» at the top right, and the drawn signature (if any) filling the rest of the cell."""

    def __init__(self, image: bytes | None, size: float, height: float):
        super().__init__()
        self.reader = ImageReader(BytesIO(image)) if image else None
        self.size = size
        self.box_height = height

    def wrap(self, avail_width, avail_height):
        self.width, self.height = avail_width, self.box_height
        return self.width, self.height

    def draw(self):
        font = _fonts(self.size)
        rtl.draw_line(self.canv, [("امضا:", rtl.BOLD)], font, x_right=self.width - 1.5, y=self.height - self.size * 1.05)
        if self.reader is None:
            return
        top = self.height - self.size * 1.6
        iw, ih = self.reader.getSize()
        scale = min((self.width - 6 * mm) / iw, top / ih)
        w, h = iw * scale, ih * scale
        self.canv.drawImage(self.reader, (self.width - w) / 2, (top - h) / 2, w, h, mask="auto")


class _BottomAnchored(Flowable):
    """Fills what is left of the frame and draws `content` flush with the frame's bottom edge,
    so the strip closes the last page instead of trailing the last element."""

    def __init__(self, content: Flowable):
        super().__init__()
        self.content = content

    def wrap(self, avail_width, avail_height):
        self.content.wrap(avail_width, avail_height)
        self.width, self.height = avail_width, avail_height
        return self.width, self.height

    def draw(self):
        self.content.drawOn(self.canv, 0, 0)


def _plain(value: str) -> str:
    """User text without the designer's inline markers, so a name is never restyled."""
    text = value or ""
    for marker in ("**", "~~", "--"):
        text = text.replace(marker, "")
    return text.strip()


def _approval_strip(data: FormPdfInput, width: float) -> list:
    """Three columns, the first signer on the right — تهیه کننده | تایید کننده | تصویب کننده.
    Each is a stack: the role, «سمت <role>: …», «نام و نام خانوادگی <role>: …», then plain «امضا:» with the signature
    (owner's request, 2026-09-30; no date, no validity). Pinned to the foot of the last page.
    Plain text — no grid, no shading (owner's correction, 2026-10-01): the Table only lines the
    columns up, so the rows of the three signers stay level."""
    size = data.base_font_size - 1
    signers = list(data.signers)
    columns = []
    for signer in signers:
        columns.append(
            [
                _cell(signer.role_label + ":", size + 1, bold=True),
                _cell(f"**سمت {signer.role_label}:** {_plain(signer.position)}".rstrip(), size, align="right"),
                _cell(f"**نام و نام خانوادگی {signer.role_label}:** {_plain(signer.name)}".rstrip(), size, align="right"),
                _SignatureCell(signer.image, size - 1, 16 * mm),
            ]
        )
    # Rows of the table; the columns reversed so the first signer sits on the right.
    rows = [[column[i] for column in reversed(columns)] for i in range(4)]
    table = Table(rows, colWidths=[width / len(columns)] * len(columns))
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("VALIGN", (0, 3), (-1, 3), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                ("LEFTPADDING", (0, 1), (-1, 2), 3),
                ("RIGHTPADDING", (0, 1), (-1, 2), 3),
                ("LEFTPADDING", (0, 3), (-1, 3), 0),
                ("RIGHTPADDING", (0, 3), (-1, 3), 0),
                ("TOPPADDING", (0, 3), (-1, 3), 0),
                ("BOTTOMPADDING", (0, 3), (-1, 3), 0),
            ]
        )
    )
    _, height = table.wrap(width, 10**6)
    return [CondPageBreak(height + 4 * mm), _BottomAnchored(table)]


def story(data: FormPdfInput, width: float, height: float = 230 * mm) -> list:
    flowables: list = []
    if data.show_letter_box:
        flowables.append(LetterBox(data.base_font_size))
    numbering = _Numbering()
    for element in data.elements:
        kind = element.get("kind")
        if kind in SIZED_BUILDERS:
            flowables.extend(SIZED_BUILDERS[kind](element, data, numbering, height))
        elif kind in BUILDERS:
            flowables.extend(BUILDERS[kind](element, data, numbering))
        # An element kind this build doesn't know is skipped, not fatal.
    if data.approval_strip and data.signers:
        flowables.extend(_approval_strip(data, width))
    return flowables


# --------------------------------------------------------------------------
# Page furniture
# --------------------------------------------------------------------------


def _draw_text(c, text, font: rtl.Font, *, x_right, y, bold=False, center_in=None):
    """One shaped line. With `center_in=(left, right)` it is centred between them."""
    line = [(text, rtl.BOLD if bold else rtl.NORMAL)]
    if center_in is not None:
        left, right = center_in
        x_right = right - ((right - left) - rtl.line_width(line, font)) / 2
    rtl.draw_line(c, line, font, x_right=x_right, y=y)


def _draw_header(c, data: FormPdfInput, page: int, total: int):
    width, height = c._pagesize
    left, right = MARGIN_SIDE * mm, width - MARGIN_SIDE * mm
    top = height - MARGIN_TOP * mm
    bottom = top - HEADER_HEIGHT * mm
    logo_left = right - LOGO_CELL * mm
    meta_right = left + META_CELL * mm

    c.saveState()
    c.setStrokeColorRGB(*LINE_COLOR)
    c.setLineWidth(0.8)
    c.rect(left, bottom, right - left, top - bottom)
    c.setLineWidth(0.5)
    c.line(logo_left, bottom, logo_left, top)
    c.line(meta_right, bottom, meta_right, top)

    if data.logo:
        box = 19 * mm
        try:
            c.drawImage(
                ImageReader(BytesIO(data.logo)),
                logo_left + (LOGO_CELL * mm - box) / 2,
                bottom + (HEADER_HEIGHT * mm - box) / 2,
                box,
                box,
                mask="auto",
                preserveAspectRatio=True,
                anchor="c",
            )
        except (OSError, ValueError):  # unreadable image: leave the cell empty
            pass

    # Middle: company name, title, subtitle, centred.
    middle = (meta_right + 2 * mm, logo_left - 2 * mm)
    c.setFillColorRGB(0, 0, 0)
    lines = []
    if data.company_name:
        lines.append((data.company_name, _fonts(9), False, MUTED))
    lines.append((data.title, _fonts(13), True, (0, 0, 0)))
    if data.subtitle:
        lines.append((data.subtitle, _fonts(8.5), False, MUTED))
    block = sum(font.size * 1.45 for _, font, _, _ in lines)
    y = bottom + (HEADER_HEIGHT * mm + block) / 2
    for text, font, bold, color in lines:
        y -= font.size * 1.45
        c.setFillColorRGB(*color)
        _draw_text(c, text, font, x_right=0, y=y + font.size * 0.3, bold=bold, center_in=middle)

    # Left column: identity of this sheet.
    meta = [f"کد: {data.full_code}", f"بازنگری: {data.revision}", f"تاریخ: {data.date}"]
    meta.append(f"صفحه {page} از {total}")
    font = _fonts(8.5)
    row = (HEADER_HEIGHT * mm) / len(meta)
    c.setFillColorRGB(0, 0, 0)
    for index, text in enumerate(meta):
        row_top = top - index * row
        if index:
            c.setStrokeColorRGB(0.75, 0.75, 0.75)
            c.setLineWidth(0.3)
            c.line(left, row_top, meta_right, row_top)
        _draw_text(c, text, font, x_right=meta_right - 2 * mm, y=row_top - row / 2 - font.size * 0.3)
    c.restoreState()


def _draw_footer(c, data: FormPdfInput):
    width, _ = c._pagesize
    left, right = MARGIN_SIDE * mm, width - MARGIN_SIDE * mm
    bottom = MARGIN_BOTTOM * mm
    top = bottom + FOOTER_HEIGHT * mm

    c.saveState()
    c.setStrokeColorRGB(*LINE_COLOR)
    c.setLineWidth(0.6)
    c.line(left, top, right, top)
    qr = FOOTER_HEIGHT * mm - 2 * mm
    if data.qr:
        c.drawImage(ImageReader(BytesIO(data.qr)), left, bottom, qr, qr, mask="auto")
    c.setFillColorRGB(*MUTED)
    y = top - 5 * mm
    if data.footnote1:
        _draw_text(c, data.footnote1, _fonts(9), x_right=right, y=y)
        y -= 4.5 * mm
    if data.footnote2:
        _draw_text(c, data.footnote2, _fonts(8), x_right=right, y=y)
    c.restoreState()


def _draw_watermark(c, text: str = PREVIEW_TEXT):
    width, height = c._pagesize
    c.saveState()
    c.setFillColorRGB(0.85, 0.85, 0.85)
    c.translate(width / 2, height / 2)
    c.rotate(45)
    c.setFont(f"{settings.PDF_FONT_NAME}-Bold", 60)
    c.drawCentredString(0, 0, rtl.shape(text))
    c.restoreState()


def _canvas_class(data: FormPdfInput):
    class FormCanvas(Canvas):
        """Holds every page until the end, then draws the header and footer on
        each — the header needs the page count («صفحه X از Y»)."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._pages = []

        def showPage(self):
            self._pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._pages)
            for number, state in enumerate(self._pages, start=1):
                self.__dict__.update(state)
                _draw_header(self, data, number, total)
                _draw_footer(self, data)
                super().showPage()
            super().save()

    return FormCanvas


def render(data: FormPdfInput, *, preview: bool = False, invariant: bool = False) -> bytes:
    pagesize = landscape(A4) if data.orientation == "landscape" else A4
    page_width, page_height = pagesize
    frame_bottom = (MARGIN_BOTTOM + FOOTER_HEIGHT + FOOTER_GAP) * mm
    frame_top = page_height - (MARGIN_TOP + HEADER_HEIGHT + HEADER_GAP) * mm
    frame_width = page_width - 2 * MARGIN_SIDE * mm
    frame = Frame(
        MARGIN_SIDE * mm,
        frame_bottom,
        frame_width,
        frame_top - frame_bottom,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
        id="body",
    )

    buffer = BytesIO()
    doc = BaseDocTemplate(
        buffer,
        pagesize=pagesize,
        title=f"{data.title} {data.full_code}",
        author="",
        creator="VEye",
        invariant=1 if invariant else 0,
    )
    # The watermark goes on first, under the page's content. «منسوخ» (a superseded revision) wins
    # over «پیش نمایش»: what matters most about the sheet is that it is no longer in force.
    mark = OBSOLETE_TEXT if data.obsolete else (PREVIEW_TEXT if preview else None)
    on_page = (lambda canvas, _doc: _draw_watermark(canvas, mark)) if mark else (lambda canvas, _doc: None)
    doc.addPageTemplates([PageTemplate(id="form", frames=[frame], onPage=on_page)])

    content = story(data, frame_width, frame_top - frame_bottom)
    if not content:
        content = [Spacer(1, 1)]  # an empty form still prints its header and footer
    doc.build(content, canvasmaker=_canvas_class(data))
    return buffer.getvalue()
