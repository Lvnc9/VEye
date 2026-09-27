"""The shape of a form body (Phase 11, ADR-011).

A form body is an ordered list of `Section` rows of type FORM_ELEMENT. Each row's
`content` is one element, `{"kind": "...", ...}`; `Document.form_settings` holds
the page settings. This module is the single place that says what a valid
element or settings object looks like. `clean_element` / `clean_settings` take
what a client sent and return the normalised dict that is stored — every
property present, defaults filled in, unknown keys dropped — or raise
`FormSchemaError` with Persian messages.

It is plain Python rather than DRF serializers because the shapes are nested
JSON (table cells, merged ranges) and the messages must name the element's
own words («ستون ۲»), which a serializer's error tree would have to be
translated back into.

Units: widths are percentages of the usable page width, heights are
millimetres, line thickness is points. Text may use the designer's rich-text
markers (**bold**, ~~italic~~, --underline--).
"""
from __future__ import annotations

from typing import Any, Callable

#: Caps. Generous for any real form; they bound what one save can make the
#: server store and the PDF renderer draw.
MAX_ELEMENTS = 300
MAX_TEXT = 5000
MAX_LABEL = 300

SETTINGS_VERSION = 1


class FormSchemaError(Exception):
    """Invalid form input. `messages` are Persian, ready for the user."""

    def __init__(self, messages: list[str]):
        super().__init__("; ".join(messages))
        self.messages = messages


class _Reader:
    """Reads typed properties out of one raw dict, collecting problems instead
    of stopping at the first, so a save reports everything wrong at once."""

    def __init__(self, raw: Any, where: str, problems: list[str] | None = None):
        self.raw = raw if isinstance(raw, dict) else {}
        self.where = where
        self.problems: list[str] = [] if problems is None else problems
        if not isinstance(raw, dict):
            self.problems.append(f"{where}: ساختار نامعتبر است.")

    def nested(self, raw: Any, where: str) -> "_Reader":
        """A reader for a dict inside this one (a table column, a field), whose
        problems are reported with this element's name first."""
        return _Reader(raw, f"{self.where} — {where}", self.problems)

    def fail(self, message: str) -> None:
        self.problems.append(f"{self.where}: {message}")

    def text(self, key: str, *, label: str, max_length: int = MAX_LABEL, default: str = "") -> str:
        value = self.raw.get(key, default)
        if value is None:
            return default
        if not isinstance(value, str):
            self.fail(f"«{label}» باید متن باشد.")
            return default
        if len(value) > max_length:
            self.fail(f"«{label}» نباید بیشتر از {_fa(max_length)} نویسه باشد.")
            return value[:max_length]
        # Stored as typed (no trimming): the author's spacing is theirs.
        return value

    def choice(self, key: str, options: tuple[str, ...], *, label: str) -> str:
        value = self.raw.get(key, options[0])
        if value not in options:
            self.fail(f"مقدار «{label}» نامعتبر است.")
            return options[0]
        return value

    def boolean(self, key: str, *, default: bool = False) -> bool:
        value = self.raw.get(key, default)
        return value if isinstance(value, bool) else default

    def number(self, key: str, *, label: str, low: float, high: float, default: float, integer=False) -> float:
        value = self.raw.get(key, default)
        # bool is an int subclass; `True` is not a size.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            self.fail(f"«{label}» باید عدد باشد.")
            return default
        if integer and int(value) != value:
            self.fail(f"«{label}» باید عدد صحیح باشد.")
            return default
        if not low <= value <= high:
            self.fail(f"«{label}» باید بین {_fa(low)} و {_fa(high)} باشد.")
            return default
        return int(value) if integer else float(value)

    def items(self, key: str, *, label: str, max_items: int, min_items: int = 0, default: list | None = None) -> list:
        value = self.raw.get(key, [] if default is None else default)
        if not isinstance(value, list):
            self.fail(f"«{label}» باید فهرست باشد.")
            return []
        if len(value) > max_items:
            self.fail(f"«{label}» نباید بیشتر از {_fa(max_items)} مورد باشد.")
            return value[:max_items]
        if len(value) < min_items:
            self.fail(f"«{label}» باید دست‌کم {_fa(min_items)} مورد داشته باشد.")
        return value


_PERSIAN_DIGITS = str.maketrans("0123456789.", "۰۱۲۳۴۵۶۷۸۹٫")


def _fa(number: float) -> str:
    text = f"{number:g}"
    return text.translate(_PERSIAN_DIGITS)


#: Widths are percentages of the row; they must add up to 100 (± this).
WIDTH_TOLERANCE = 0.5


def _widths(reader: _Reader, widths: list[float], *, label: str) -> None:
    """Checks one row's widths add up to the whole row."""
    if widths and abs(sum(widths) - 100) > WIDTH_TOLERANCE:
        reader.fail(f"مجموع پهنای {label} باید ۱۰۰ درصد باشد (اکنون {_fa(round(sum(widths), 1))}).")


# --------------------------------------------------------------------------
# Elements
# --------------------------------------------------------------------------

ALIGNMENTS = ("right", "center", "left")


def _heading(r: _Reader) -> dict:
    return {
        "text": r.text("text", label="عنوان"),
        "style": r.choice("style", ("band", "underline", "plain"), label="شکل عنوان"),
        "level": r.number("level", label="سطح عنوان", low=1, high=3, default=1, integer=True),
        "numbered": r.boolean("numbered"),
        "align": r.choice("align", ("right", "center"), label="چینش"),
    }


def _text(r: _Reader) -> dict:
    return {
        "text": r.text("text", label="متن", max_length=MAX_TEXT),
        "align": r.choice("align", ALIGNMENTS, label="چینش"),
        # 0 = the form's base size.
        "size": r.number("size", label="اندازه قلم", low=0, high=20, default=0, integer=True),
        "boxed": r.boolean("boxed"),
    }


def _divider(r: _Reader) -> dict:
    return {
        "style": r.choice("style", ("solid", "dashed", "dotted", "double"), label="نوع خط"),
        "thickness": r.number("thickness", label="ضخامت خط", low=0.25, high=3, default=0.75),
        "space_before": r.number("space_before", label="فاصله از بالا", low=0, high=30, default=2),
        "space_after": r.number("space_after", label="فاصله از پایین", low=0, high=30, default=2),
    }


def _spacer(r: _Reader) -> dict:
    return {"height": r.number("height", label="ارتفاع فاصله", low=1, high=150, default=5)}


def _page_break(r: _Reader) -> dict:
    return {}


#: What the blank after a field's label looks like on paper.
FIELD_TYPES = ("text", "date", "national_code", "phone", "checkbox")
MAX_FIELD_ROWS = 40
MAX_FIELDS_PER_ROW = 6
MIN_WIDTH = 5


def _fields(r: _Reader) -> dict:
    """A grid of labelled blanks — «نام: ________  نام خانوادگی: ________»."""
    default_rows = [
        {"cells": [{"label": "نام", "width": 50}, {"label": "نام خانوادگی", "width": 50}]},
    ]
    rows = []
    for row_number, raw_row in enumerate(
        r.items("rows", label="ردیف‌ها", max_items=MAX_FIELD_ROWS, min_items=1, default=default_rows), start=1
    ):
        row = r.nested(raw_row, f"ردیف {_fa(row_number)}")
        cells = []
        for cell_number, raw_cell in enumerate(
            row.items("cells", label="خانه‌ها", max_items=MAX_FIELDS_PER_ROW, min_items=1), start=1
        ):
            cell = row.nested(raw_cell, f"خانه {_fa(cell_number)}")
            cells.append(
                {
                    "label": cell.text("label", label="برچسب"),
                    "type": cell.choice("type", FIELD_TYPES, label="نوع خانه"),
                    "width": cell.number("width", label="پهنا", low=MIN_WIDTH, high=100, default=100),
                }
            )
        _widths(row, [c["width"] for c in cells], label="خانه‌های این ردیف")
        rows.append({"cells": cells})
    return {
        "rows": rows,
        "blank": r.choice("blank", ("underline", "dotted", "box"), label="شکل جای خالی"),
        "row_height": r.number("row_height", label="ارتفاع ردیف", low=6, high=20, default=9),
        "photo": r.boolean("photo"),
    }


def _answer_box(r: _Reader) -> dict:
    """Room for a written answer: ruled lines, or an empty frame of a height."""
    return {
        "label": r.text("label", label="عنوان"),
        "lines": r.number("lines", label="تعداد خط", low=0, high=25, default=4, integer=True),
        "height": r.number("height", label="ارتفاع کادر", low=10, high=200, default=30),
        "line_style": r.choice("line_style", ("dotted", "solid"), label="نوع خط"),
        "framed": r.boolean("framed", default=True),
    }


def _signatures(r: _Reader) -> dict:
    """A row of signature boxes, and optionally a box for the stamp (مهر)."""
    default_boxes = [{"caption": "امضای تکمیل‌کننده"}]
    boxes = []
    for number, raw_box in enumerate(
        r.items("boxes", label="کادرهای امضا", max_items=4, min_items=1, default=default_boxes), start=1
    ):
        box = r.nested(raw_box, f"کادر {_fa(number)}")
        boxes.append(
            {
                "caption": box.text("caption", label="عنوان کادر"),
                "name_line": box.boolean("name_line", default=True),
                "date_line": box.boolean("date_line", default=True),
            }
        )
    return {
        "boxes": boxes,
        "stamp": r.boolean("stamp"),
        "height": r.number("height", label="ارتفاع کادر", low=15, high=60, default=28),
    }


MAX_COLUMNS = 20
MAX_TABLE_ROWS = 300
MAX_HEADER_ROWS = 3
MAX_CELL = 1000
MIN_COLUMN_WIDTH = 4
COLUMN_TYPES = ("text", "row_number", "checkbox", "date")


def _text_grid(r: _Reader, key: str, *, label: str, columns: int, max_rows: int, min_rows: int, default) -> list[list[str]]:
    """Rows of cell texts, each exactly `columns` long."""
    grid = []
    for row_number, raw_row in enumerate(
        r.items(key, label=label, max_items=max_rows, min_items=min_rows, default=default), start=1
    ):
        where = f"{label} — ردیف {_fa(row_number)}"
        if not isinstance(raw_row, list):
            r.fail(f"{where}: ساختار نامعتبر است.")
            continue
        if len(raw_row) != columns:
            r.fail(f"{where}: تعداد خانه‌ها باید با تعداد ستون‌ها ({_fa(columns)}) برابر باشد.")
            continue
        row = []
        for column_number, value in enumerate(raw_row, start=1):
            if not isinstance(value, str):
                r.fail(f"{where}، ستون {_fa(column_number)}: متن خانه باید متن باشد.")
                value = ""
            elif len(value) > MAX_CELL:
                r.fail(f"{where}، ستون {_fa(column_number)}: متن خانه نباید بیشتر از {_fa(MAX_CELL)} نویسه باشد.")
                value = value[:MAX_CELL]
            row.append(value)
        grid.append(row)
    return grid


MAX_MERGES = 200


def _merges(r: _Reader, *, header_rows: int, grid_rows: int, columns: int) -> list[dict]:
    """Merged cells over the header and the written rows (grid row 0 is the
    first header row). A merge stays inside the header or inside the body,
    covers at least two cells, and no two merges overlap."""
    merges, taken = [], {}
    for number, raw in enumerate(r.items("merges", label="ادغام‌ها", max_items=MAX_MERGES), start=1):
        merge = r.nested(raw, f"ادغام {_fa(number)}")
        row = merge.number("row", label="ردیف", low=0, high=max(grid_rows - 1, 0), default=0, integer=True)
        col = merge.number("col", label="ستون", low=0, high=columns - 1, default=0, integer=True)
        rowspan = merge.number("rowspan", label="تعداد ردیف", low=1, high=grid_rows, default=1, integer=True)
        colspan = merge.number("colspan", label="تعداد ستون", low=1, high=columns, default=1, integer=True)
        if grid_rows == 0:
            merge.fail("جدول ردیفی برای ادغام ندارد.")
            continue
        if row + rowspan > grid_rows or col + colspan > columns:
            merge.fail("از جدول بیرون می‌زند.")
            continue
        if rowspan * colspan < 2:
            merge.fail("دست‌کم دو خانه را در بر بگیرد.")
            continue
        if row < header_rows < row + rowspan:
            merge.fail("سرستون و ردیف‌های جدول را با هم ادغام نمی‌کند.")
            continue
        cells = {(y, x) for y in range(row, row + rowspan) for x in range(col, col + colspan)}
        clash = next((taken[cell] for cell in cells if cell in taken), None)
        if clash is not None:
            merge.fail(f"با ادغام {_fa(clash)} هم‌پوشانی دارد.")
            continue
        taken.update({cell: number for cell in cells})
        merges.append({"row": row, "col": col, "rowspan": rowspan, "colspan": colspan})
    return merges


def _table(r: _Reader) -> dict:
    """A table with a 1–3 row header, rows written in advance, and blank rows
    to fill by hand. Column 1 is the rightmost."""
    default_columns = [
        {"width": 10, "type": "row_number", "align": "center"},
        {"width": 60},
        {"width": 30},
    ]
    columns = []
    for number, raw in enumerate(
        r.items("columns", label="ستون‌ها", max_items=MAX_COLUMNS, min_items=1, default=default_columns), start=1
    ):
        column = r.nested(raw, f"ستون {_fa(number)}")
        columns.append(
            {
                "width": column.number("width", label="پهنا", low=MIN_COLUMN_WIDTH, high=100, default=100),
                "align": column.choice("align", ALIGNMENTS, label="چینش"),
                "type": column.choice("type", COLUMN_TYPES, label="نوع ستون"),
            }
        )
    _widths(r, [c["width"] for c in columns], label="ستون‌ها")
    count = len(columns)
    default_header = [["ردیف", "عنوان", "توضیحات"]] if count == 3 else [[""] * count]
    header = _text_grid(r, "header", label="سرستون", columns=count, max_rows=MAX_HEADER_ROWS, min_rows=1, default=default_header)
    rows = _text_grid(r, "rows", label="ردیف‌های متن‌دار", columns=count, max_rows=MAX_TABLE_ROWS, min_rows=0, default=[])
    blank_rows = r.number("blank_rows", label="ردیف‌های خالی", low=0, high=MAX_TABLE_ROWS, default=5, integer=True)
    if len(rows) + blank_rows > MAX_TABLE_ROWS:
        r.fail(f"یک جدول نمی‌تواند بیش از {_fa(MAX_TABLE_ROWS)} ردیف داشته باشد.")
    merges = _merges(r, header_rows=len(header), grid_rows=len(header) + len(rows), columns=count)
    return {
        "title": r.text("title", label="عنوان جدول"),
        "columns": columns,
        "header": header,
        "rows": rows,
        "blank_rows": blank_rows,
        "row_height": r.number("row_height", label="ارتفاع ردیف", low=5, high=30, default=8),
        "font_size": r.number("font_size", label="اندازه قلم", low=0, high=14, default=0, integer=True),
        "borders": r.choice("borders", ("all", "outer", "horizontal", "none"), label="خطوط جدول"),
        "header_shade": r.boolean("header_shade", default=True),
        "repeat_header": r.boolean("repeat_header", default=True),
        "merges": merges,
    }


#: kind → (Persian name, cleaner). The Persian name is how errors refer to it.
ELEMENTS: dict[str, tuple[str, Callable[[_Reader], dict]]] = {
    "heading": ("عنوان بخش", _heading),
    "text": ("متن", _text),
    "divider": ("خط جداکننده", _divider),
    "spacer": ("فاصله", _spacer),
    "page_break": ("شکست صفحه", _page_break),
    "fields": ("فیلدها", _fields),
    "answer_box": ("کادر پاسخ", _answer_box),
    "signatures": ("امضا", _signatures),
    "table": ("جدول", _table),
}


def element_label(kind: str) -> str:
    entry = ELEMENTS.get(kind)
    return entry[0] if entry else "جزء ناشناخته"


def clean_element(raw: Any, *, number: int) -> dict:
    """The stored form of one element. `number` is its 1-based position, for messages."""
    kind = raw.get("kind") if isinstance(raw, dict) else None
    entry = ELEMENTS.get(kind)
    if entry is None:
        raise FormSchemaError([f"جزء {_fa(number)}: نوع جزء فرم نامعتبر است."])
    name, cleaner = entry
    reader = _Reader(raw, f"جزء {_fa(number)} ({name})")
    cleaned = cleaner(reader)
    if reader.problems:
        raise FormSchemaError(reader.problems)
    return {"kind": kind, **cleaned}


def normalize_stored(content: dict) -> dict:
    """A stored element as the current schema describes it. Elements saved
    before a property existed gain it with its default (a table saved before
    merged cells has `merges: []`), so readers — the designer, the PDF — never
    meet a missing key. Stored data that no longer passes the rules is returned
    as it is rather than hidden; the next save reports what to fix."""
    try:
        return clean_element(content, number=1)
    except FormSchemaError:
        return content


# --------------------------------------------------------------------------
# Page settings
# --------------------------------------------------------------------------


def clean_settings(raw: Any) -> dict:
    reader = _Reader(raw if raw is not None else {}, "تنظیمات صفحه")
    header = _Reader(reader.raw.get("header", {}), "سربرگ فرم")
    cleaned = {
        "v": SETTINGS_VERSION,
        "orientation": reader.choice("orientation", ("portrait", "landscape"), label="جهت صفحه"),
        "base_font_size": reader.number(
            "base_font_size", label="اندازه قلم", low=8, high=14, default=10, integer=True
        ),
        "approval_strip": reader.boolean("approval_strip", default=True),
        "header": {
            "subtitle": header.text("subtitle", label="زیرعنوان سربرگ", max_length=255),
            "show_company_name": header.boolean("show_company_name", default=True),
            "show_letter_box": header.boolean("show_letter_box", default=False),
        },
    }
    problems = reader.problems + header.problems
    if problems:
        raise FormSchemaError(problems)
    return cleaned


def normalize_stored_settings(settings: dict) -> dict:
    """Stored page settings as the current schema describes them (see
    `normalize_stored`)."""
    try:
        return clean_settings(settings or {})
    except FormSchemaError:
        return settings


def default_settings() -> dict:
    return clean_settings({})
