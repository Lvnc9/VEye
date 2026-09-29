"""The rich body of a تشریحی بلند block (owner's request, 2026-09-29): a Word-like document
made in the designer's editor (Tiptap / ProseMirror) and printed by `apps.pdfgen.richtext`.

Stored in `Section.content["rich"] = {"v": 1, "doc": {...}}` next to the old `body` /
`extra_boxes` marker text, which is still what a block without `rich` prints.

Whatever the editor sends is checked against a **whitelist** — the editor may only offer
what the renderer prints, so anything else is refused rather than silently dropped:

  nodes  paragraph · heading (1-3) · bulletList · orderedList · listItem · table · tableRow ·
         tableCell · tableHeader · horizontalRule · pageBreak · hardBreak · text
  marks  bold · italic · underline · strike · textStyle (fontSize, color) · link
  attrs  textAlign (right|center|left|justify) and indent (0-6) on paragraphs and headings,
         start on an orderedList, colwidth on a cell; a merged cell (colspan/rowspan > 1) is refused.

`clean` returns a normalised copy (unknown attributes removed, defaults dropped); `plain_text`
is the text the search and the legacy `body` mirror keep.
"""
from __future__ import annotations

import re

#: Text colours the editor offers (lower-case hex). The renderer draws any of them.
PALETTE = ("#000000", "#4b5563", "#dc2626", "#ea580c", "#16a34a", "#1d4ed8", "#7e22ce")
FONT_SIZES = (8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32)
MIN_FONT_SIZE, MAX_FONT_SIZE = min(FONT_SIZES), max(FONT_SIZES)
ALIGNMENTS = ("right", "center", "left", "justify")
MAX_INDENT = 6
MAX_DEPTH = 12
MAX_LIST_DEPTH = 3
MAX_NODES = 20_000
MAX_TEXT = 100_000  # the same ceiling as the marker body
MAX_COLUMNS = 20
MAX_ROWS = 200
VERSION = 1

_LINK = re.compile(r"^(https?://|mailto:)[^\s\x00-\x1f\x7f<>\"']{1,2000}$", re.IGNORECASE)
_BLOCKS = {"paragraph", "heading", "bulletList", "orderedList", "table", "horizontalRule", "pageBreak"}
_CELL_BLOCKS = {"paragraph", "heading", "bulletList", "orderedList"}
_MARKS = {"bold", "italic", "underline", "strike", "textStyle", "link"}


class RichContentError(ValueError):
    """The document breaks the whitelist; the message is Persian and shown to the user."""


def _refuse(message: str):
    raise RichContentError(message)


class _Counter:
    def __init__(self):
        self.nodes = 0
        self.text = 0

    def node(self):
        self.nodes += 1
        if self.nodes > MAX_NODES:
            _refuse("متن بلند بیش از حد پیچیده است؛ آن را کوتاه‌تر کنید.")


def _attrs(node: dict, allowed: set[str]) -> dict:
    attrs = node.get("attrs") or {}
    if not isinstance(attrs, dict):
        _refuse("ساختار متن نامعتبر است.")
    return {key: value for key, value in attrs.items() if key in allowed}


def _clean_block_attrs(node: dict, *, level: bool = False) -> dict:
    attrs = _attrs(node, {"textAlign", "indent", "level"})
    out: dict = {}
    align = attrs.get("textAlign")
    if align not in (None, "right"):  # right is the RTL default
        if align not in ALIGNMENTS:
            _refuse("چیدمان متن نامعتبر است.")
        out["textAlign"] = align
    indent = attrs.get("indent", 0)
    if not isinstance(indent, int) or isinstance(indent, bool) or not 0 <= indent <= MAX_INDENT:
        _refuse("میزان تورفتگی نامعتبر است.")
    if indent:
        out["indent"] = indent
    if level:
        value = attrs.get("level")
        if not isinstance(value, int) or isinstance(value, bool) or value not in (1, 2, 3):
            _refuse("سطح عنوان باید ۱ تا ۳ باشد.")
        out["level"] = value
    return out


def _clean_mark(mark: dict) -> dict:
    if not isinstance(mark, dict) or mark.get("type") not in _MARKS:
        _refuse("قالب‌بندی متن پشتیبانی نمی‌شود.")
    kind = mark["type"]
    if kind == "textStyle":
        attrs = _attrs(mark, {"fontSize", "color"})
        out = {}
        size = attrs.get("fontSize")
        if size is not None:
            if isinstance(size, bool) or not isinstance(size, (int, float)) or not MIN_FONT_SIZE <= size <= MAX_FONT_SIZE:
                _refuse(f"اندازهٔ قلم باید بین {MIN_FONT_SIZE} و {MAX_FONT_SIZE} باشد.")
            out["fontSize"] = int(size) if float(size).is_integer() else float(size)
        color = attrs.get("color")
        if color is not None:
            if not isinstance(color, str) or color.lower() not in PALETTE:
                _refuse("رنگ متن نامعتبر است.")
            out["color"] = color.lower()
        return {"type": "textStyle", "attrs": out} if out else {}
    if kind == "link":
        href = _attrs(mark, {"href"}).get("href")
        if not isinstance(href, str) or not _LINK.match(href):
            _refuse("نشانی پیوند باید با http://، https:// یا mailto: شروع شود.")
        return {"type": "link", "attrs": {"href": href}}
    if mark.get("attrs"):
        _refuse("قالب‌بندی متن نامعتبر است.")
    return {"type": kind}


def _clean_inline(nodes, counter: _Counter, depth: int) -> list[dict]:
    if nodes is None:
        return []
    if not isinstance(nodes, list):
        _refuse("ساختار متن نامعتبر است.")
    out = []
    for node in nodes:
        counter.node()
        if not isinstance(node, dict):
            _refuse("ساختار متن نامعتبر است.")
        kind = node.get("type")
        if kind == "hardBreak":
            out.append({"type": "hardBreak"})
        elif kind == "text":
            text = node.get("text")
            if not isinstance(text, str):
                _refuse("ساختار متن نامعتبر است.")
            counter.text += len(text)
            if counter.text > MAX_TEXT:
                _refuse("متن بلند از حد مجاز طولانی‌تر است.")
            if not text:
                continue
            marks = node.get("marks") or []
            if not isinstance(marks, list) or len(marks) > 8:
                _refuse("قالب‌بندی متن نامعتبر است.")
            cleaned = [m for m in (_clean_mark(mark) for mark in marks) if m]
            if len({m["type"] for m in cleaned}) != len(cleaned):
                _refuse("قالب‌بندی متن نامعتبر است.")
            item = {"type": "text", "text": text}
            if cleaned:
                item["marks"] = cleaned
            out.append(item)
        else:
            _refuse("این بخش متن پشتیبانی نمی‌شود.")
    return out


def _clean_children(nodes, allowed: set[str], counter: _Counter, depth: int, list_depth: int) -> list[dict]:
    if nodes is None:
        return []
    if not isinstance(nodes, list):
        _refuse("ساختار متن نامعتبر است.")
    return [_clean_block(node, allowed, counter, depth, list_depth) for node in nodes]


def _clean_block(node, allowed: set[str], counter: _Counter, depth: int, list_depth: int) -> dict:
    counter.node()
    if depth > MAX_DEPTH:
        _refuse("متن بلند بیش از حد تودرتو است.")
    if not isinstance(node, dict) or node.get("type") not in allowed:
        _refuse("این بخش متن پشتیبانی نمی‌شود.")
    kind = node["type"]

    if kind in ("paragraph", "heading"):
        out: dict = {"type": kind}
        attrs = _clean_block_attrs(node, level=kind == "heading")
        if attrs:
            out["attrs"] = attrs
        content = _clean_inline(node.get("content"), counter, depth + 1)
        if content:
            out["content"] = content
        return out

    if kind in ("horizontalRule", "pageBreak"):
        return {"type": kind}

    if kind in ("bulletList", "orderedList"):
        if list_depth >= MAX_LIST_DEPTH:
            _refuse(f"فهرست‌ها حداکثر {MAX_LIST_DEPTH} سطح می‌توانند تودرتو باشند.")
        out = {"type": kind}
        if kind == "orderedList":
            start = _attrs(node, {"start"}).get("start", 1)
            if not isinstance(start, int) or isinstance(start, bool) or not 1 <= start <= 9999:
                _refuse("شمارهٔ شروع فهرست نامعتبر است.")
            if start != 1:
                out["attrs"] = {"start": start}
        items = []
        for item in node.get("content") or []:
            counter.node()
            if not isinstance(item, dict) or item.get("type") != "listItem":
                _refuse("ساختار فهرست نامعتبر است.")
            children = _clean_children(
                item.get("content"), {"paragraph", "bulletList", "orderedList"}, counter, depth + 2, list_depth + 1
            )
            items.append({"type": "listItem", "content": children})
        if not items:
            _refuse("فهرست خالی است.")
        out["content"] = items
        return out

    # table
    rows_in = node.get("content") or []
    if not isinstance(rows_in, list) or not rows_in:
        _refuse("جدول باید دست‌کم یک ردیف داشته باشد.")
    if len(rows_in) > MAX_ROWS:
        _refuse(f"جدول حداکثر {MAX_ROWS} ردیف می‌تواند داشته باشد.")
    rows, width = [], None
    for row in rows_in:
        counter.node()
        if not isinstance(row, dict) or row.get("type") != "tableRow":
            _refuse("ساختار جدول نامعتبر است.")
        cells_in = row.get("content") or []
        if not isinstance(cells_in, list) or not cells_in:
            _refuse("ردیف جدول خالی است.")
        if len(cells_in) > MAX_COLUMNS:
            _refuse(f"جدول حداکثر {MAX_COLUMNS} ستون می‌تواند داشته باشد.")
        if width is None:
            width = len(cells_in)
        elif len(cells_in) != width:
            _refuse("همهٔ ردیف‌های جدول باید تعداد ستون یکسان داشته باشند.")
        cells = []
        for cell in cells_in:
            counter.node()
            if not isinstance(cell, dict) or cell.get("type") not in ("tableCell", "tableHeader"):
                _refuse("ساختار جدول نامعتبر است.")
            attrs = _attrs(cell, {"colspan", "rowspan", "colwidth"})
            if attrs.get("colspan", 1) != 1 or attrs.get("rowspan", 1) != 1:
                _refuse("ادغام خانه‌های جدول پشتیبانی نمی‌شود.")
            clean_cell: dict = {"type": cell["type"]}
            colwidth = attrs.get("colwidth")
            if colwidth is not None:
                if (
                    not isinstance(colwidth, list)
                    or len(colwidth) != 1
                    or isinstance(colwidth[0], bool)
                    or not isinstance(colwidth[0], (int, float))
                    or not 20 <= colwidth[0] <= 2000
                ):
                    _refuse("عرض ستون جدول نامعتبر است.")
                clean_cell["attrs"] = {"colwidth": [round(colwidth[0])]}
            children = _clean_children(cell.get("content"), _CELL_BLOCKS, counter, depth + 3, list_depth)
            clean_cell["content"] = children or [{"type": "paragraph"}]
            cells.append(clean_cell)
        rows.append({"type": "tableRow", "content": cells})
    return {"type": "table", "content": rows}


def clean(rich) -> dict:
    """Validate `{"v": 1, "doc": {...}}` and return its normalised copy; raise RichContentError."""
    if not isinstance(rich, dict) or rich.get("v") != VERSION:
        _refuse("نسخهٔ قالب متن نامعتبر است.")
    doc = rich.get("doc")
    if not isinstance(doc, dict) or doc.get("type") != "doc":
        _refuse("ساختار متن نامعتبر است.")
    counter = _Counter()
    content = _clean_children(doc.get("content"), _BLOCKS, counter, 1, 0)
    return {"v": VERSION, "doc": {"type": "doc", "content": content}}


def _inline_text(node: dict) -> str:
    parts = []
    for child in node.get("content") or []:
        parts.append("\n" if child.get("type") == "hardBreak" else child.get("text", ""))
    return "".join(parts)


def _block_lines(node: dict) -> list[str]:
    kind = node.get("type")
    if kind in ("paragraph", "heading"):
        return _inline_text(node).split("\n")
    if kind in ("bulletList", "orderedList"):
        return [line for item in node.get("content") or [] for child in item.get("content") or [] for line in _block_lines(child)]
    if kind == "table":
        rows = []
        for row in node.get("content") or []:
            cells = [" ".join(line for child in cell.get("content") or [] for line in _block_lines(child) if line)
                     for cell in row.get("content") or []]
            rows.append("\t".join(cells))
        return rows
    return []  # rules and page breaks carry no text


def plain_text(rich: dict) -> str:
    """The text of a rich body, one paragraph (list item, table row) per line — what `body`
    mirrors for search and for readers that only know the old marker text."""
    lines = [line for node in rich.get("doc", {}).get("content") or [] for line in _block_lines(node)]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip("\n")


def is_blank(rich: dict | None) -> bool:
    """True for no document or one with no text, table or rule."""
    if not rich:
        return True
    return not _has_content(rich.get("doc", {}))


def _has_content(node: dict) -> bool:
    kind = node.get("type")
    if kind == "text":
        return bool(node.get("text", "").strip())
    if kind in ("table", "horizontalRule", "pageBreak"):
        return True
    return any(_has_content(child) for child in node.get("content") or [])
