"""The sign-off strip on the last page of a پوستر (owner's request, 2026-09-30).

Three columns, right to left: تهیه کننده | تایید کننده | تصویب کننده. Each is a stack —
the role, then «سمت: …», then «نام و نام خانوادگی: …», then «امضا:» with the drawn
signature — and the strip is pinned to the foot of the last page, above the footer.
No date and no validity: whether a document is still in force is the watermark's job.

Drawn through `rtl.py` (each run shaped on its own, drawn from the right edge), never
through V_1.0's `prepare_rtl` + `drawString`, so a label and its value keep their order.
The block renderer's `PDFMaker.draw_signoff_strip` decodes the signature images and
calls `draw`; nothing here touches module state.
"""
from __future__ import annotations

from reportlab.pdfbase import pdfmetrics

from . import rtl

#: What each column says, right to left. (`SignOffRole.label` says «تدوین کننده» for the
#: first — the owner asked for «تهیه کننده» on paper.)
ROLES = ("تهیه کننده", "تایید کننده", "تصویب کننده")

SIZE = 9.5
TITLE_SIZE = 11.0
PAD = 6.0
LEADING = 1.5
TITLE_ROW = 24.0
MIN_ROW = 24.0
SIGNATURE_ROW = 62.0
#: The strip's bottom edge: the footer's QR reaches y = 90, so this leaves a small gap.
BOTTOM = 108.0
#: Content must end at least this far above the strip, or the strip goes on a new page.
GAP = 14.0
LINE_WIDTH = 0.6
TITLE_FILL = 0.92


def _fonts(font_name: str, size: float) -> rtl.Font:
    bold = font_name + "-Bold"
    if bold not in pdfmetrics.getRegisteredFontNames():
        bold = font_name
    return rtl.Font(font_name, bold, size)


def _plain(value) -> str:
    """User text without the designer's inline markers (`**`, `~~`, `--`), so a name is never restyled."""
    text = str(value or "")
    for marker in ("**", "~~", "--"):
        text = text.replace(marker, "")
    return text.strip()


def _lines(label: str, value, font: rtl.Font, width: float) -> list[rtl.Line]:
    """«label: value», the label bold, wrapped to `width`; just the label when there is no value."""
    text = f"**{label}**" + (f" {_plain(value)}" if _plain(value) else "")
    return rtl.wrap(text, font, width)


def measure(font_name: str, signers: list, column_width: float):
    """(rows, heights): per row the wrapped lines of each column (right to left), and the row heights.
    `signers` are [name, post, signature] triples, first signer rightmost."""
    font = _fonts(font_name, SIZE)
    inner = column_width - 2 * PAD
    posts = [_lines("سمت:", s[1], font, inner) for s in signers]
    names = [_lines("نام و نام خانوادگی:", s[0], font, inner) for s in signers]
    rows = [posts, names]
    heights = [TITLE_ROW]
    for row in rows:
        most = max(len(lines) for lines in row)
        heights.append(max(MIN_ROW, most * SIZE * LEADING + 2 * PAD - 2))
    heights.append(SIGNATURE_ROW)
    return rows, heights


def height_of(font_name: str, signers: list, column_width: float) -> float:
    return sum(measure(font_name, signers, column_width)[1])


def draw(maker, signers: list, images: list) -> None:
    """Draw the strip on `maker`'s current page — or, when the content already reaches into its
    place, on a new one — with its bottom edge at `BOTTOM`."""
    maker.initialize_first_page()
    c = maker.c
    x1 = maker.page_width - maker.margin
    column_width = (x1 - maker.margin) / len(ROLES)
    rows, heights = measure(maker.font_name, signers, column_width)
    top = BOTTOM + sum(heights)
    if maker.current_y - GAP < top:
        maker._new_page()

    regular, small = _fonts(maker.font_name, SIZE), _fonts(maker.font_name, 8.0)
    title_font = _fonts(maker.font_name, TITLE_SIZE)
    c.saveState()
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(LINE_WIDTH)

    y = top
    for row, height in enumerate(heights):
        for index in range(len(ROLES)):
            x_right = x1 - index * column_width
            x_left = x_right - column_width
            if row == 0:
                c.setFillColorRGB(TITLE_FILL, TITLE_FILL, TITLE_FILL)
                c.rect(x_left, y - height, column_width, height, fill=1, stroke=1)
            else:
                c.rect(x_left, y - height, column_width, height, fill=0, stroke=1)
            c.setFillColorRGB(0, 0, 0)

            if row == 0:
                line = [(ROLES[index] + ":", rtl.BOLD)]
                x = x_right - (column_width - rtl.line_width(line, title_font)) / 2
                rtl.draw_line(c, line, title_font, x_right=x, y=y - height / 2 - TITLE_SIZE * 0.32)
            elif row <= len(rows):
                baseline = y - PAD - SIZE * 0.85
                for line in rows[row - 1][index]:
                    rtl.draw_line(c, line, regular, x_right=x_right - PAD, y=baseline)
                    baseline -= SIZE * LEADING
            else:  # the signature cell
                rtl.draw_line(c, [("امضا:", rtl.BOLD)], small, x_right=x_right - PAD, y=y - PAD - 8.0 * 0.85)
                image = images[index]
                if image is not None:
                    box_w, box_h = column_width - 2 * PAD - 8, height - PAD - 14
                    c.drawImage(
                        image, x_left + (column_width - box_w) / 2, y - height + PAD / 2, box_w, box_h,
                        mask="auto", preserveAspectRatio=True, anchor="c",
                    )
        y -= height
    c.restoreState()
    c.setFillColorRGB(0, 0, 0)
    maker.current_y = BOTTOM
