"""Right-to-left text for the form renderer (Phase 11): wrapping, shaping and
drawing Persian lines with the designer's inline markers.

The order of operations is the whole point. Text is wrapped while it is still
in *logical* order — measuring each candidate line by the width of its shaped
glyphs — and only then is each finished line shaped (`arabic_reshaper`) and
reordered for display (`bidi.get_display`). Reordering a paragraph first and
wrapping the result puts its lines in reverse order and splits words from the
wrong end.

Markers (**bold**, ~~italic~~, --underline--) are the ones the block designer
stores and V_1.0's renderer parses. A line is drawn as runs from the right edge
leftwards, in logical order, each run shaped on its own; `renderer.py` (the
owner's, left as it is) lays runs out left to right instead.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.pdfbase.pdfmetrics import stringWidth

NORMAL, BOLD, ITALIC, UNDERLINE = "normal", "bold", "italic", "underline"

_MARKERS = re.compile(r"(\*\*.*?\*\*|~~.*?~~|--.*?--)")
_STYLE_OF = {"**": BOLD, "~~": ITALIC, "--": UNDERLINE}
_SPACE = re.compile(r"(\s+)")

#: Degrees of slant for italic, since Vazir has no italic face.
_ITALIC_SLANT = 12


def shape(text: str) -> str:
    """One line, ready for `drawString`: joined letter forms, visual order."""
    return get_display(arabic_reshaper.reshape(text))


def runs(text: str) -> list[tuple[str, str]]:
    """Split one line into (text, style) runs, markers removed. Styles do not
    nest (the designer refuses nesting)."""
    result = []
    for fragment in _MARKERS.split(text):
        if not fragment:
            continue
        style = _STYLE_OF.get(fragment[:2]) if len(fragment) >= 4 and fragment[:2] == fragment[-2:] else None
        if style:
            result.append((fragment[2:-2], style))
        else:
            result.append((fragment, NORMAL))
    return result


def strip_markers(text: str) -> str:
    return "".join(part for part, _ in runs(text))


@dataclass(frozen=True)
class Font:
    regular: str
    bold: str
    size: float

    def face(self, style: str) -> str:
        return self.bold if style == BOLD else self.regular

    def width(self, text: str, style: str = NORMAL) -> float:
        # Shaping changes glyphs (and so widths); reordering does not.
        return stringWidth(arabic_reshaper.reshape(text), self.face(style), self.size)


Line = list[tuple[str, str]]


def wrap(text: str, font: Font, width: float, *, bold: bool = False) -> list[Line]:
    """Logical lines of (text, style) runs, each at most `width` wide.

    Hard line breaks are kept; an empty paragraph stays an empty line. A single
    word wider than the line is cut between characters rather than overflowing.
    `bold` sets the whole text in bold (unmarked runs become BOLD).
    """
    lines: list[Line] = []
    for paragraph in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        # Atoms: words and the spaces between them, each with its style.
        atoms: list[tuple[str, str]] = []
        for part, style in runs(paragraph):
            if bold and style == NORMAL:
                style = BOLD
            atoms.extend((piece, style) for piece in _SPACE.split(part) if piece)

        current: Line = []
        used = 0.0
        for atom, style in atoms:
            is_space = atom.isspace()
            atom_width = font.width(atom, style)
            if used + atom_width <= width or (not current and not is_space and atom_width <= width):
                if current or not is_space:  # no leading space on a line
                    current.append((atom, style))
                    used += atom_width
                continue
            if is_space:  # the break itself: drop the space
                lines.append(_trim(current))
                current, used = [], 0.0
                continue
            if current:
                lines.append(_trim(current))
                current, used = [], 0.0
            if atom_width <= width:
                current, used = [(atom, style)], atom_width
                continue
            # One word longer than the line: cut it.
            piece = ""
            for char in atom:
                if piece and font.width(piece + char, style) > width:
                    lines.append([(piece, style)])
                    piece = ""
                piece += char
            current, used = [(piece, style)], font.width(piece, style)
        lines.append(_trim(current))
    return [_merge(line) for line in lines]


def _trim(line: Line) -> Line:
    while line and line[-1][0].isspace():
        line = line[:-1]
    return line


def _merge(line: Line) -> Line:
    """Join neighbouring atoms of the same style back into one run, so a run is
    shaped as a whole (letters join across it, embedded Latin keeps its order)."""
    merged: Line = []
    for text, style in line:
        if merged and merged[-1][1] == style:
            merged[-1] = (merged[-1][0] + text, style)
        else:
            merged.append((text, style))
    return merged


def line_width(line: Line, font: Font) -> float:
    return sum(font.width(text, style) for text, style in line)


def draw_line(canvas, line: Line, font: Font, *, x_right: float, y: float) -> None:
    """Draw one wrapped line with its right edge at `x_right`. Runs go right to
    left in logical order: the first run is the rightmost."""
    x = x_right
    for text, style in line:
        visual = shape(text)
        face = font.face(style)
        run_width = stringWidth(visual, face, font.size)
        x -= run_width
        canvas.saveState()
        canvas.setFont(face, font.size)
        if style == ITALIC:
            canvas.translate(x, y)
            # skew(alpha, beta) maps (x, y) → (x + tan(beta)·y, …): tops lean over.
            canvas.skew(0, _ITALIC_SLANT)
            canvas.drawString(0, 0, visual)
        else:
            canvas.drawString(x, y, visual)
        if style == UNDERLINE:
            canvas.setLineWidth(max(0.4, font.size / 20))
            canvas.line(x, y - font.size * 0.18, x + run_width, y - font.size * 0.18)
        canvas.restoreState()
