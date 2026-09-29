"""The boxed page header of پوستر / روش اجرایی / دستورالعمل (owner's request, 2026-09-29).

One table, the same on every page: a thick outer border, the logo in the right
cell, the title (bold, centred both ways) in the middle and — stacked in the left
cell, split by thin lines — «کد», «شماره بازنگری» and «تاریخ». It reproduces
`ST-01-01 - بیانیه خط مشی کیفیت.pdf`, the sheet the owner holds up as clean.

Everything is drawn through `rtl.py` (each run shaped on its own, drawn from the
right edge leftwards), never through V_1.0's `prepare_rtl` + `drawString`, so a
label and its value keep their reading order.
"""
from reportlab.pdfbase import pdfmetrics

from . import rtl

#: The whole box is `HEIGHT` tall; `renderer.HEADER_GAP` keeps the body below it.
HEIGHT = 66.0
ROWS = 3
LOGO_CELL = 84.0
META_CELL = 150.0
OUTER_WIDTH = 1.6
INNER_WIDTH = 0.6
PADDING = 9.0

_TITLE_SIZES = (15.0, 13.5, 12.0, 10.5, 9.5)
_MAX_TITLE_LINES = 2
_META_SIZE = 10.5


def _fonts(font_name: str, size: float) -> rtl.Font:
    bold = font_name + "-Bold"
    if bold not in pdfmetrics.getRegisteredFontNames():  # V_1.0 crashed here
        bold = font_name
    return rtl.Font(font_name, bold, size)


def _wrap_title(title: str, font_name: str, width: float) -> tuple[rtl.Font, list[str]]:
    """The largest size at which the title fits in two lines of `width`; the
    smallest size (cut into as many lines as it takes) when none does. Words are
    measured in the bold face the title is drawn in. Titles are plain text, so
    `**` or `--` inside one are not markers."""
    words = title.split()
    lines: list[str] = []
    font = _fonts(font_name, _TITLE_SIZES[-1])
    for size in _TITLE_SIZES:
        font = _fonts(font_name, size)
        lines, current = [], ""
        for word in words:
            candidate = f"{current} {word}" if current else word
            if not current or font.width(candidate, rtl.BOLD) <= width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        if len(lines) <= _MAX_TITLE_LINES and all(font.width(line, rtl.BOLD) <= width for line in lines):
            return font, lines
    return font, lines


def meta_rows(code: str, review: str, date: str) -> list[str]:
    """The three left-cell rows, «برچسب: مقدار» each."""
    return [f"کد: {code}", f"شماره بازنگری: {review}", f"تاریخ: {date}"]


def _split_label(row: str) -> tuple[str, str]:
    label, sep, value = row.partition(":")
    if not sep:
        return "", row
    return label + ":", value.strip()


def draw_boxed_header(canvas, *, title, rows, logo, font_name, x0, x1, top):
    """Draw the header with its top edge at `top` and its sides at x0 (left) / x1
    (right). `rows` are the three left-cell lines; `logo` is an `ImageReader` or
    None (an empty cell — V_1.0's black placeholder square would spoil the page).
    Colours are set here and the graphics state restored."""
    bottom = top - HEIGHT
    logo_x = x1 - LOGO_CELL
    meta_x = x0 + META_CELL

    canvas.saveState()
    canvas.setStrokeColorRGB(0, 0, 0)
    canvas.setFillColorRGB(0, 0, 0)
    canvas.setLineWidth(INNER_WIDTH)
    canvas.line(logo_x, bottom, logo_x, top)
    canvas.line(meta_x, bottom, meta_x, top)
    row_height = HEIGHT / ROWS
    for index in range(1, ROWS):
        y = top - index * row_height
        canvas.line(x0, y, meta_x, y)
    canvas.setLineWidth(OUTER_WIDTH)
    canvas.rect(x0, bottom, x1 - x0, HEIGHT)

    if logo is not None:
        try:
            box_w, box_h = LOGO_CELL - 2 * PADDING, HEIGHT - 2 * PADDING + 2
            canvas.drawImage(
                logo, logo_x + PADDING, bottom + (HEIGHT - box_h) / 2, box_w, box_h,
                mask="auto", preserveAspectRatio=True, anchor="c",
            )
        except (OSError, ValueError):  # an unreadable image leaves the cell empty
            pass

    # Title: centred in the middle cell, as large as fits in two lines.
    left, right = meta_x + PADDING, logo_x - PADDING
    font, lines = _wrap_title(title, font_name, right - left)
    lead = font.size * 1.55
    y = bottom + (HEIGHT + lead * (len(lines) - 1)) / 2 - font.size * 0.32
    for text in lines:
        line = [(text, rtl.BOLD)]
        x_right = right - ((right - left) - rtl.line_width(line, font)) / 2
        rtl.draw_line(canvas, line, font, x_right=x_right, y=y)
        y -= lead

    # Left cell: label in bold, then its value.
    font = _fonts(font_name, _META_SIZE)
    for index, row in enumerate(list(rows)[:ROWS]):
        label, value = _split_label(row)
        line = ([(label, rtl.BOLD)] if label else []) + [((" " if label else "") + value, rtl.NORMAL)]
        baseline = top - index * row_height - row_height / 2 - font.size * 0.32
        rtl.draw_line(canvas, line, font, x_right=meta_x - PADDING, y=baseline)
    canvas.restoreState()
