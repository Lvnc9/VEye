"""The compact form PDF (Phase 11, ADR-011).

A فرم is a controlled blank to be printed and filled in by hand. Unlike the
owner's renderer (`renderer.py`, which gives page 1 to a big header and the
control table), the form starts on page 1, and every page carries the form's
identity so a loose sheet is still identifiable:

* a header band — logo, title, company name / subtitle, and a column with the
  code, revision, date, validity and «صفحه X از Y»;
* a footer — the two footnotes and the QR code of the verify page;
* on a preview, the «پیش نمایش» watermark;
* after the last element, once, the approval strip (تدوین / تایید / تصویب).

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
from reportlab.platypus import BaseDocTemplate, Flowable, Frame, KeepTogether, PageBreak, PageTemplate, Spacer, Table, TableStyle

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

PREVIEW_TEXT = "پیش نمایش"


@dataclass(frozen=True)
class Signer:
    role_label: str
    name: str = ""
    position: str = ""
    date: str = ""
    image: bytes | None = None


@dataclass(frozen=True)
class FormPdfInput:
    title: str
    full_code: str
    revision: str
    date: str
    validation: str = ""
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


BUILDERS = {
    "heading": _heading,
    "text": _text,
    "divider": _divider,
    "spacer": _spacer,
    "page_break": _page_break,
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


def _approval_strip(data: FormPdfInput, width: float) -> list:
    """Three columns, تدوین on the right: role, name, سمت, date, signature."""
    size = data.base_font_size - 1
    signers = list(data.signers)
    columns = []
    for signer in signers:
        columns.append(
            [
                _cell(signer.role_label, size, bold=True),
                _cell(signer.name, size),
                _cell(signer.position, size, color=MUTED),
                _cell(signer.date, size),
                _Image(signer.image, 30 * mm, 12 * mm) if signer.image else Spacer(1, 12 * mm),
            ]
        )
    # Rows of the table; the columns reversed so the first signer sits on the right.
    rows = [[column[i] for column in reversed(columns)] for i in range(5)]
    table = Table(rows, colWidths=[width / len(columns)] * len(columns))
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, LINE_COLOR),
                ("BACKGROUND", (0, 0), (-1, 0), BAND_FILL),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
            ]
        )
    )
    return [Spacer(1, 6 * mm), KeepTogether([table])]


def story(data: FormPdfInput, width: float) -> list:
    flowables: list = []
    if data.show_letter_box:
        flowables.append(LetterBox(data.base_font_size))
    numbering = _Numbering()
    for element in data.elements:
        builder = BUILDERS.get(element.get("kind"))
        if builder is not None:  # an element kind this build doesn't know is skipped, not fatal
            flowables.extend(builder(element, data, numbering))
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
    if data.validation:
        meta.append(f"وضعیت: {data.validation}")
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


def _draw_watermark(c):
    width, height = c._pagesize
    c.saveState()
    c.setFillColorRGB(0.85, 0.85, 0.85)
    c.translate(width / 2, height / 2)
    c.rotate(45)
    c.setFont(f"{settings.PDF_FONT_NAME}-Bold", 60)
    c.drawCentredString(0, 0, rtl.shape(PREVIEW_TEXT))
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
    # The watermark goes on first, under the page's content.
    on_page = (lambda canvas, _doc: _draw_watermark(canvas)) if preview else (lambda canvas, _doc: None)
    doc.addPageTemplates([PageTemplate(id="form", frames=[frame], onPage=on_page)])

    content = story(data, frame_width)
    if not content:
        content = [Spacer(1, 1)]  # an empty form still prints its header and footer
    doc.build(content, canvasmaker=_canvas_class(data))
    return buffer.getvalue()
