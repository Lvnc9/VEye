"""Prints the rich body of a تشریحی بلند block (owner's request, 2026-09-29).

The input is the validated ProseMirror document of `apps.documents.rich_content`; the output
is drawn on `PDFMaker`'s canvas at its `current_y`, page break by page break. The legacy marker
text (`PDFMaker.add_body_text`) is untouched and still prints every block that has no `rich`.

Like `rtl.py` — which it builds on — text is wrapped while still in *logical* order, measuring
each candidate by the width of its shaped glyphs, and only finished lines are shaped and
reordered. A line is drawn as runs from its right edge leftwards, so the first run is the
rightmost. What it adds: any font size per run, colours, bold + italic + underline + strike
together (italic is a real 12° slant, unlike the legacy 0.27° shear), right / centre / left /
justified paragraphs, indents, headings, nested bullet and numbered lists, links (clickable
in the PDF), rules, page breaks and tables whose rows split across pages.

Layout is two steps: `_layout` turns nodes into measured lines (so a table row's height is
known before it is drawn), then `_Flow` draws them, breaking pages as it goes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace

import arabic_reshaper
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth

from . import rtl

FONT = "Vazir"
BASE_SIZE = 12.0
LEADING = 1.6  # a line is this many times its largest font size tall
ASCENT = 1.2  # baseline sits this many font sizes below the line's top
HEADING_SIZES = {1: 18.0, 2: 16.0, 3: 14.0}
INDENT_STEP = 24.0
LIST_STEP = 22.0  # each nested list is this much further in
MARKER_GAP = 18.0  # a list item's text starts this far in from its marker
CELL_PAD = 4.0
MIN_CELL_HEIGHT = 22.0
LINK_COLOR = "#1d4ed8"
BOTTOM = 105.0  # lines end above this (the footer's QR reaches y = 90)
PARAGRAPH_GAP = 6.0
BLOCK_GAP = 14.0  # after the whole rich body
BULLETS = ("•", "–", "·")  # by list depth; all in Vazir

_SPACES = re.compile(r"(\s+)")
_BREAK = object()


@dataclass(frozen=True)
class Style:
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strike: bool = False
    size: float = BASE_SIZE
    color: str = "#000000"
    link: str | None = None


Run = tuple[str, Style]


@dataclass
class Line:
    runs: list[Run]
    width: float  # natural width
    height: float
    align: str = "right"
    last: bool = True  # last line of its paragraph: justified text stays ragged here
    right_offset: float = 0.0  # gap between the text area's right edge and this line
    avail: float = 0.0
    marker: tuple[str, float] | None = None  # (text, size) drawn at the marker column
    marker_offset: float = 0.0


@dataclass
class Para:
    lines: list[Line]
    before: float = 0.0
    after: float = PARAGRAPH_GAP
    keep_next: bool = False  # a heading: never last on a page


@dataclass
class Rule:
    pass


@dataclass
class Break:
    pass


@dataclass
class Table:
    columns: list[float]  # widths, right to left in reading order
    rows: list[list["Cell"]]


@dataclass
class Cell:
    lines: list[Line]
    header: bool = False
    height: float = 0.0


def _bold_face() -> str:
    bold = FONT + "-Bold"
    return bold if bold in pdfmetrics.getRegisteredFontNames() else FONT


def _face(style: Style) -> str:
    return _bold_face() if style.bold else FONT


def _width(text: str, style: Style) -> float:
    return stringWidth(arabic_reshaper.reshape(text), _face(style), style.size)


def _rgb(color: str) -> tuple[float, float, float]:
    return tuple(int(color[i : i + 2], 16) / 255 for i in (1, 3, 5))  # type: ignore[return-value]


# --------------------------------------------------------------------------
# Nodes → measured lines
# --------------------------------------------------------------------------


def _style_of(marks, base: Style) -> Style:
    style = base
    for mark in marks or ():
        kind = mark["type"]
        attrs = mark.get("attrs") or {}
        if kind == "bold":
            style = replace(style, bold=True)
        elif kind == "italic":
            style = replace(style, italic=True)
        elif kind == "underline":
            style = replace(style, underline=True)
        elif kind == "strike":
            style = replace(style, strike=True)
        elif kind == "textStyle":
            if "fontSize" in attrs:
                style = replace(style, size=float(attrs["fontSize"]))
            if "color" in attrs:
                style = replace(style, color=attrs["color"])
        elif kind == "link":
            style = replace(style, link=attrs["href"])
    if style.link and not any(m["type"] == "textStyle" and "color" in (m.get("attrs") or {}) for m in marks or ()):
        style = replace(style, color=LINK_COLOR)
    if style.link:
        style = replace(style, underline=True)
    return style


def _atoms(node: dict, base: Style) -> list:
    """Words and the spaces between them (with their style), and `_BREAK` at a hard break."""
    atoms: list = []
    for child in node.get("content") or ():
        if child["type"] == "hardBreak":
            atoms.append(_BREAK)
            continue
        style = _style_of(child.get("marks"), base)
        for piece in _SPACES.split(child.get("text", "")):
            if piece:
                atoms.append((piece, style))
    return atoms


def _merge(runs: list[Run]) -> list[Run]:
    merged: list[Run] = []
    for text, style in runs:
        if merged and merged[-1][1] == style:
            merged[-1] = (merged[-1][0] + text, style)
        else:
            merged.append((text, style))
    return merged


def _wrap(atoms: list, width: float) -> list[tuple[list[Run], bool]]:
    """[(runs, ends_paragraph)] — lines at most `width` wide, wrapped between words (a word
    wider than the line is cut between characters). A hard break ends a line early."""
    lines: list[tuple[list[Run], bool]] = []
    current: list[Run] = []
    used = 0.0

    def flush(last: bool):
        nonlocal current, used
        while current and current[-1][0].isspace():
            current = current[:-1]
        lines.append((_merge(current), last))
        current, used = [], 0.0

    for atom in atoms:
        if atom is _BREAK:
            flush(True)
            continue
        text, style = atom
        size = _width(text, style)
        if text.isspace():
            if current and used + size <= width:
                current.append((text, style))
                used += size
            elif current:
                flush(False)
            continue
        if used + size <= width:
            current.append((text, style))
            used += size
            continue
        if current:
            flush(False)
        if size <= width:
            current, used = [(text, style)], size
            continue
        piece = ""
        for char in text:  # one word wider than the line
            if piece and _width(piece + char, style) > width:
                lines.append(([(piece, style)], False))
                piece = ""
            piece += char
        current, used = [(piece, style)], _width(piece, style)
    flush(True)
    return lines


def _line(runs: list[Run], last: bool, *, align: str, right_offset: float, avail: float, base_size: float) -> Line:
    size = max((style.size for _, style in runs), default=base_size)
    return Line(
        runs=runs,
        width=sum(_width(text, style) for text, style in runs),
        height=size * LEADING,
        align=align,
        last=last,
        right_offset=right_offset,
        avail=avail,
    )


def _paragraph(node: dict, *, width: float, right_offset: float, base: Style, align_default="right") -> Para:
    attrs = node.get("attrs") or {}
    indent = attrs.get("indent", 0) * INDENT_STEP
    avail = max(width - indent, 30.0)
    wrapped = _wrap(_atoms(node, base), avail)
    align = attrs.get("textAlign", align_default)
    lines = [
        _line(runs, last, align=align, right_offset=right_offset + indent, avail=avail, base_size=base.size)
        for runs, last in wrapped
    ]
    return Para(lines)


def _heading(node: dict, *, width: float, right_offset: float) -> Para:
    level = node["attrs"]["level"]
    base = Style(bold=True, size=HEADING_SIZES[level])
    para = _paragraph(node, width=width, right_offset=right_offset, base=base)
    para.before = 8.0
    para.after = 4.0
    para.keep_next = True
    return para


def _list_item_marker(kind: str, number: int, depth: int) -> str:
    return f"{number}." if kind == "orderedList" else BULLETS[min(depth, len(BULLETS) - 1)]


def _list(node: dict, *, width: float, right_offset: float, depth: int) -> list:
    items: list = []
    number = (node.get("attrs") or {}).get("start", 1)
    inner_offset = right_offset + MARKER_GAP
    inner_width = width - MARKER_GAP
    for item in node["content"]:
        first = True
        for child in item["content"]:
            produced = _blocks([child], width=inner_width, right_offset=inner_offset, depth=depth + 1)
            if first and produced and isinstance(produced[0], Para) and produced[0].lines:
                head = produced[0].lines[0]
                head.marker = (_list_item_marker(node["type"], number, depth), max(BASE_SIZE, head.height / LEADING))
                head.marker_offset = right_offset
                first = False
            items.extend(produced)
        number += 1
    for produced in items:  # tighter: no gap between the items of one list
        if isinstance(produced, Para):
            produced.after = min(produced.after, 2.0)
    if items and isinstance(items[-1], Para):
        items[-1].after = PARAGRAPH_GAP
    return items


def _blocks(nodes: list, *, width: float, right_offset: float = 0.0, depth: int = 0, in_cell: bool = False) -> list:
    out: list = []
    for node in nodes:
        kind = node["type"]
        if kind == "paragraph":
            out.append(_paragraph(node, width=width, right_offset=right_offset, base=Style()))
        elif kind == "heading":
            out.append(_heading(node, width=width, right_offset=right_offset))
        elif kind in ("bulletList", "orderedList"):
            out.extend(_list(node, width=width, right_offset=right_offset, depth=depth))
        elif kind == "horizontalRule":
            out.append(Rule())
        elif kind == "pageBreak":
            out.append(Break())
        elif kind == "table":
            out.append(_table(node, width=width))
    return out


def _table(node: dict, *, width: float) -> Table:
    first = node["content"][0]["content"]
    widths = [(cell.get("attrs") or {}).get("colwidth", [None])[0] for cell in first]
    if all(widths):
        scale = width / sum(widths)
        columns = [w * scale for w in widths]
    else:
        columns = [width / len(first)] * len(first)
    rows = []
    for row in node["content"]:
        cells = []
        for column, cell in zip(columns, row["content"]):
            header = cell["type"] == "tableHeader"
            inner = max(column - 2 * CELL_PAD, 20.0)
            items = []
            for child in cell["content"]:
                if child["type"] == "paragraph":
                    para = _paragraph(child, width=inner, right_offset=0.0, base=Style(bold=header))
                    items.append(para)
                elif child["type"] == "heading":
                    items.append(_heading(child, width=inner, right_offset=0.0))
                else:
                    items.extend(_blocks([child], width=inner, depth=0, in_cell=True))
            lines = []
            for para in items:
                lines.extend(para.lines)
            height = sum(line.height for line in lines)
            cells.append(Cell(lines=lines, header=header, height=height))
        rows.append(cells)
    return Table(columns=columns, rows=rows)


# --------------------------------------------------------------------------
# Drawing
# --------------------------------------------------------------------------


class _Flow:
    """Draws laid-out items on a `PDFMaker`'s canvas from its `current_y` down, on new pages as needed."""

    def __init__(self, maker):
        self.maker = maker
        self.c = maker.c
        self.left = maker.margin
        self.right = maker.page_width - maker.margin
        self.cursor = maker.current_y

    # -- pages --------------------------------------------------------------

    def new_page(self):
        self.maker._new_page()
        self.cursor = self.maker.current_y

    def room(self) -> float:
        return self.cursor - BOTTOM

    def ensure(self, height: float):
        if self.room() < height:
            self.new_page()

    # -- items --------------------------------------------------------------

    def draw(self, items: list):
        for index, item in enumerate(items):
            if isinstance(item, Para):
                self._para(item, items[index + 1] if index + 1 < len(items) else None, first=index == 0)
            elif isinstance(item, Rule):
                self.ensure(20)
                y = self.cursor - 8
                self.c.saveState()
                self.c.setStrokeColorRGB(0.35, 0.35, 0.35)
                self.c.setLineWidth(0.8)
                self.c.line(self.left, y, self.right, y)
                self.c.restoreState()
                self.cursor -= 16
            elif isinstance(item, Break):
                self.new_page()
            elif isinstance(item, Table):
                self._table(item)

    def _para(self, para: Para, following, *, first: bool):
        if not first and self.cursor < self.maker.current_y:  # not at the top of a page
            self.cursor -= para.before
        if not para.lines:
            return
        need = para.lines[0].height
        if para.keep_next and isinstance(following, Para) and following.lines:
            need += following.lines[0].height
        if self.room() < need:
            self.new_page()
        for line in para.lines:
            if self.room() < line.height:
                self.new_page()
            self.line(line, self.cursor, x_right=self.right, x_left=self.left)
            self.cursor -= line.height
        self.cursor -= para.after

    def line(self, line: Line, top: float, *, x_right: float, x_left: float):
        """One line whose top is `top`, inside the area [x_left, x_right]."""
        baseline = top - max((s.size for _, s in line.runs), default=BASE_SIZE) * ASCENT
        area_right = x_right - line.right_offset
        area_left = area_right - line.avail if line.avail else x_left
        extra_per_space = 0.0
        if line.align == "justify" and not line.last and line.runs:
            spaces = sum(text.count(" ") for text, _ in line.runs)
            if spaces and line.avail > line.width:
                extra_per_space = (line.avail - line.width) / spaces
        width = line.width + extra_per_space * sum(text.count(" ") for text, _ in line.runs)
        if line.align == "center":
            right = area_right - (area_right - area_left - width) / 2
        elif line.align == "left":
            right = area_left + width
        else:  # right, and justify (whose full lines run edge to edge)
            right = area_right
        if line.marker:
            text, size = line.marker
            style = Style(size=size)
            self._run(text, style, x_right=x_right - line.marker_offset, baseline=baseline, extra=0.0)
        x = right
        for text, style in line.runs:
            x -= self._run(text, style, x_right=x, baseline=baseline, extra=extra_per_space)

    def _run(self, text: str, style: Style, *, x_right: float, baseline: float, extra: float) -> float:
        """Draw one run with its right edge at `x_right`; return the width it took."""
        visual = rtl.shape(text)
        face = _face(style)
        pieces = visual.split(" ") if extra else [visual]
        space = stringWidth(" ", face, style.size) + extra
        width = sum(stringWidth(piece, face, style.size) for piece in pieces) + space * (len(pieces) - 1)
        x_left = x_right - width
        c = self.c
        c.saveState()
        c.setFont(face, style.size)
        color = _rgb(style.color)
        c.setFillColorRGB(*color)
        c.setStrokeColorRGB(*color)
        x = x_left
        for piece in pieces:
            if style.italic:
                c.saveState()
                c.translate(x, baseline)
                c.skew(0, rtl._ITALIC_SLANT)
                c.drawString(0, 0, piece)
                c.restoreState()
            else:
                c.drawString(x, baseline, piece)
            x += stringWidth(piece, face, style.size) + space
        thickness = max(0.4, style.size / 20)
        if style.underline:
            c.setLineWidth(thickness)
            c.line(x_left, baseline - style.size * 0.18, x_right, baseline - style.size * 0.18)
        if style.strike:
            c.setLineWidth(thickness)
            c.line(x_left, baseline + style.size * 0.3, x_right, baseline + style.size * 0.3)
        if style.link:
            c.linkURL(style.link, (x_left, baseline - style.size * 0.25, x_right, baseline + style.size * 0.9), relative=0, thickness=0)
        c.restoreState()
        return width

    # -- tables ---------------------------------------------------------------

    def _table(self, table: Table):
        self.cursor -= 2
        total = sum(table.columns)
        for row in table.rows:
            self._row(table, row, total)
        self.cursor -= PARAGRAPH_GAP + 4

    def _row(self, table: Table, row: list[Cell], total: float):
        pending = [list(cell.lines) for cell in row]
        page_text_height = self.maker.page_height - self.maker.margin - self.maker.header_gap - BOTTOM
        while True:
            natural = max(
                max((sum(line.height for line in lines) for lines in pending), default=0) + 2 * CELL_PAD,
                MIN_CELL_HEIGHT,
            )
            if natural > self.room() and natural <= page_text_height:
                self.new_page()  # the row fits on a page of its own
            if natural <= self.room():
                take, pending, height = pending, [[] for _ in pending], natural
            else:  # a row taller than a page: draw what fits, carry the rest to the next page
                if self.room() < MIN_CELL_HEIGHT + 30:
                    self.new_page()
                budget = self.room() - 2 * CELL_PAD
                take = []
                for lines in pending:
                    used, part = 0.0, []
                    while lines and used + lines[0].height <= budget:
                        used += lines[0].height
                        part.append(lines.pop(0))
                    take.append(part)
                if not any(take):  # nothing fits even here: one line, so the loop always advances
                    for lines, part in zip(pending, take):
                        if lines:
                            part.append(lines.pop(0))
                            break
                height = max(max((sum(l.height for l in part) for part in take), default=0) + 2 * CELL_PAD, MIN_CELL_HEIGHT)
            self._draw_row(table, row, take, height)
            self.cursor -= height
            if not any(pending):
                return
            self.new_page()

    def _draw_row(self, table: Table, row: list[Cell], lines_per_cell: list[list[Line]], height: float):
        c = self.c
        x_right = self.right
        top = self.cursor
        for column, cell, lines in zip(table.columns, row, lines_per_cell):
            x_left = x_right - column
            c.saveState()
            c.setLineWidth(0.6)
            c.setStrokeColorRGB(0, 0, 0)
            if cell.header:
                c.setFillColorRGB(0.92, 0.92, 0.92)
                c.rect(x_left, top - height, column, height, fill=1, stroke=1)
            else:
                c.rect(x_left, top - height, column, height, fill=0, stroke=1)
            c.restoreState()
            y = top - CELL_PAD
            for line in lines:
                self.line(line, y, x_right=x_right - CELL_PAD, x_left=x_left + CELL_PAD)
                y -= line.height
            x_right = x_left


def render(maker, heading: str, doc: dict) -> None:
    """Print a تشریحی بلند block's heading (bold, 14 pt, as the legacy block does) and rich body."""
    maker.initialize_first_page()
    width = maker.page_width - 2 * maker.margin
    items: list = []
    if heading and heading.strip():
        title = {"type": "heading", "attrs": {"level": 3}, "content": [{"type": "text", "text": heading.strip()}]}
        items.append(_heading(title, width=width, right_offset=0.0))
        items[0].before = 0.0
    items.extend(_blocks(doc.get("content", []), width=width))
    flow = _Flow(maker)
    flow.draw(items)
    maker.current_y = flow.cursor - BLOCK_GAP
    maker.c.setFillColorRGB(0, 0, 0)
    maker.c.setStrokeColorRGB(0, 0, 0)
    maker.idx_texts += 1
