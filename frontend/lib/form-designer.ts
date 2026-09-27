/**
 * The form designer's state logic (Phase 11, ADR-011), kept free of React like
 * lib/designer.ts: element defaults, server response ↔ editable state, the save
 * payload, local checks, reordering and heading numbering.
 *
 * The element shapes mirror backend/apps/documents/form_schema.py, which is the
 * authority: whatever is sent is normalised there and comes back in the response.
 */
import { newKey } from "./designer";
import type { ContentResponse } from "./types";

export const FORM_ELEMENT = "Form Element" as const;
export const MAX_ELEMENTS = 300;
export const MAX_TEXT = 5000;
export const MAX_LABEL = 300;

export type Align = "right" | "center" | "left";

export interface HeadingProps {
  kind: "heading";
  text: string;
  style: "band" | "underline" | "plain";
  level: 1 | 2 | 3;
  numbered: boolean;
  align: "right" | "center";
}

export interface TextProps {
  kind: "text";
  text: string;
  align: Align;
  /** 0 = the form's base size. */
  size: number;
  boxed: boolean;
}

export interface DividerProps {
  kind: "divider";
  style: "solid" | "dashed" | "dotted" | "double";
  /** Points. */
  thickness: number;
  /** Millimetres. */
  space_before: number;
  space_after: number;
}

export interface SpacerProps {
  kind: "spacer";
  /** Millimetres. */
  height: number;
}

export interface PageBreakProps {
  kind: "page_break";
}

/** What the blank after a field's label looks like on paper. */
export type FieldType = "text" | "date" | "national_code" | "phone" | "checkbox";

export const FIELD_TYPE_LABELS: Record<FieldType, string> = {
  text: "متن",
  date: "تاریخ (…/…/…)",
  national_code: "کد ملی (۱۰ خانه)",
  phone: "تلفن همراه (۱۱ خانه)",
  checkbox: "گزینهٔ تیک‌زدنی",
};

export interface FieldCell {
  label: string;
  type: FieldType;
  /** Percent of the row; a row's cells add up to 100. */
  width: number;
}

export interface FieldsProps {
  kind: "fields";
  rows: { cells: FieldCell[] }[];
  blank: "underline" | "dotted" | "box";
  /** Millimetres. */
  row_height: number;
  /** A 3×4 photo box on the left. */
  photo: boolean;
}

export interface AnswerBoxProps {
  kind: "answer_box";
  label: string;
  /** Ruled lines; 0 = an empty frame of `height`. */
  lines: number;
  /** Millimetres. */
  height: number;
  line_style: "dotted" | "solid";
  framed: boolean;
}

export interface SignatureBox {
  caption: string;
  name_line: boolean;
  date_line: boolean;
}

export interface SignaturesProps {
  kind: "signatures";
  boxes: SignatureBox[];
  stamp: boolean;
  /** Millimetres. */
  height: number;
}

export type ColumnType = "text" | "row_number" | "checkbox" | "date";

export const COLUMN_TYPE_LABELS: Record<ColumnType, string> = {
  text: "متن",
  row_number: "شمارهٔ ردیف",
  checkbox: "گزینهٔ تیک‌زدنی",
  date: "تاریخ (…/…/…)",
};

export interface TableColumn {
  /** Percent of the table; the columns add up to 100. */
  width: number;
  align: Align;
  type: ColumnType;
}

/** A merged range; `row` counts the header rows first, then the written rows. */
export interface Merge {
  row: number;
  col: number;
  rowspan: number;
  colspan: number;
}

export interface TableProps {
  kind: "table";
  title: string;
  columns: TableColumn[];
  /** 1–3 header rows, one text per column. */
  header: string[][];
  /** Rows written in advance (printed text), one text per column. */
  rows: string[][];
  /** Empty rows after them, to fill in by hand. */
  blank_rows: number;
  /** Millimetres; the least height of a body row. */
  row_height: number;
  /** 0 = one point under the form's base size. */
  font_size: number;
  borders: "all" | "outer" | "horizontal" | "none";
  header_shade: boolean;
  repeat_header: boolean;
  merges: Merge[];
}

export const MAX_COLUMNS = 20;
export const MAX_TABLE_ROWS = 300;
export const MAX_HEADER_ROWS = 3;
export const MAX_CELL = 1000;
/** Narrowest column, percent (form_schema.MIN_COLUMN_WIDTH). */
export const MIN_COLUMN_WIDTH = 4;

export const MAX_FIELD_ROWS = 40;
export const MAX_FIELDS_PER_ROW = 6;
export const MAX_SIGNATURE_BOXES = 4;
/** Narrowest field cell, percent (form_schema.MIN_WIDTH). */
export const MIN_FIELD_WIDTH = 5;

export type ElementProps =
  | HeadingProps
  | TextProps
  | DividerProps
  | SpacerProps
  | PageBreakProps
  | FieldsProps
  | AnswerBoxProps
  | SignaturesProps
  | TableProps;
export type ElementKind = ElementProps["kind"];

/** An element being edited: its props plus a React key and, once saved, its id. */
export type FormElement = ElementProps & { key: string; id?: number };

export interface FormSettings {
  v: number;
  orientation: "portrait" | "landscape";
  base_font_size: number;
  approval_strip: boolean;
  header: {
    subtitle: string;
    show_company_name: boolean;
    show_letter_box: boolean;
  };
}

export interface FormState {
  version: number;
  footnote1: string;
  footnote2: string;
  settings: FormSettings;
  elements: FormElement[];
}

/** The palette: every kind, its Persian name, and which group it is listed under. */
export const ELEMENT_KINDS: { kind: ElementKind; label: string; group: "structure" | "input" | "sign" }[] = [
  { kind: "heading", label: "عنوان بخش", group: "structure" },
  { kind: "text", label: "متن", group: "structure" },
  { kind: "divider", label: "خط جداکننده", group: "structure" },
  { kind: "spacer", label: "فاصله", group: "structure" },
  { kind: "page_break", label: "شکست صفحه", group: "structure" },
  { kind: "fields", label: "فیلدها", group: "input" },
  { kind: "answer_box", label: "کادر پاسخ", group: "input" },
  { kind: "table", label: "جدول", group: "input" },
  { kind: "signatures", label: "امضا", group: "sign" },
];

export const ELEMENT_GROUP_LABELS = { structure: "ساختار", input: "ورود اطلاعات", sign: "امضا" } as const;

export function elementLabel(kind: ElementKind): string {
  return ELEMENT_KINDS.find((entry) => entry.kind === kind)?.label ?? kind;
}

/** A fresh element with the same defaults the server fills in (form_schema.py). */
export function newElement(kind: ElementKind): FormElement {
  const key = newKey();
  switch (kind) {
    case "heading":
      return { key, kind, text: "عنوان بخش", style: "band", level: 1, numbered: false, align: "right" };
    case "text":
      return { key, kind, text: "", align: "right", size: 0, boxed: false };
    case "divider":
      return { key, kind, style: "solid", thickness: 0.75, space_before: 2, space_after: 2 };
    case "spacer":
      return { key, kind, height: 5 };
    case "page_break":
      return { key, kind };
    case "fields":
      return {
        key,
        kind,
        rows: [
          {
            cells: [
              { label: "نام", type: "text", width: 50 },
              { label: "نام خانوادگی", type: "text", width: 50 },
            ],
          },
        ],
        blank: "underline",
        row_height: 9,
        photo: false,
      };
    case "answer_box":
      return { key, kind, label: "", lines: 4, height: 30, line_style: "dotted", framed: true };
    case "signatures":
      return {
        key,
        kind,
        boxes: [{ caption: "امضای تکمیل‌کننده", name_line: true, date_line: true }],
        stamp: false,
        height: 28,
      };
    case "table":
      return {
        key,
        kind,
        title: "",
        columns: [
          { width: 10, align: "center", type: "row_number" },
          { width: 60, align: "right", type: "text" },
          { width: 30, align: "right", type: "text" },
        ],
        header: [["ردیف", "عنوان", "توضیحات"]],
        rows: [],
        blank_rows: 5,
        row_height: 8,
        font_size: 0,
        borders: "all",
        header_shade: true,
        repeat_header: true,
        merges: [],
      };
  }
}

// ---------------------------------------------------------------------------
// Widths (percent of a row; field cells now, table columns later)
// ---------------------------------------------------------------------------

const round1 = (n: number) => Math.round(n * 10) / 10;

/** `n` equal widths that add up to exactly 100. */
export function evenWidths(n: number): number[] {
  if (n <= 0) return [];
  const each = Math.floor(1000 / n) / 10;
  const widths = Array.from({ length: n }, () => each);
  widths[n - 1] = round1(100 - each * (n - 1));
  return widths;
}

/**
 * Moves the border between cell `index` and cell `index + 1` by `delta`
 * percent: cell `index` grows by `delta` and its neighbour shrinks by the same,
 * neither below `min`. The total never changes.
 */
export function moveBoundary(widths: number[], index: number, delta: number, min: number): number[] {
  if (index < 0 || index + 1 >= widths.length) return widths;
  const a = widths[index];
  const b = widths[index + 1];
  const clamped = Math.max(min - a, Math.min(b - min, delta));
  const next = widths.slice();
  next[index] = round1(a + clamped);
  next[index + 1] = round1(a + b - next[index]);
  return next;
}

/**
 * Converts a horizontal drag of a border into a width change of the column on
 * its right (in RTL, column `index` sits right of column `index + 1`): dragging
 * the border left (dx < 0) widens that column.
 */
export function dragToDelta(dx: number, tableWidthPx: number): number {
  if (tableWidthPx <= 0) return 0;
  return (-dx / tableWidthPx) * 100;
}

/** Widths after adding a column at the end: it takes half of the widest column
 *  (or everything is evened out when that would be too narrow). */
export function widthsWithColumnAdded(widths: number[], min: number): number[] {
  if (widths.length === 0) return [100];
  const widest = widths.indexOf(Math.max(...widths));
  const half = round1(widths[widest] / 2);
  if (half < min) return evenWidths(widths.length + 1);
  const next = widths.slice();
  next[widest] = round1(widths[widest] - half);
  return [...next, half];
}

/** Widths after removing column `index`: its width goes to its neighbour. */
export function widthsWithColumnRemoved(widths: number[], index: number): number[] {
  if (widths.length <= 1) return widths;
  const next = widths.slice();
  const [gone] = next.splice(index, 1);
  const neighbour = Math.min(index, next.length - 1);
  next[neighbour] = round1(next[neighbour] + gone);
  return next;
}

/** Sets cell `index` to `value` percent, taking the difference from its
 *  neighbour (the next cell, or the previous one for the last). */
export function setWidth(widths: number[], index: number, value: number, min: number): number[] {
  if (widths.length < 2) return widths;
  const delta = value - widths[index];
  if (index + 1 < widths.length) return moveBoundary(widths, index, delta, min);
  return moveBoundary(widths, index - 1, -delta, min);
}

export function defaultSettings(): FormSettings {
  return {
    v: 1,
    orientation: "portrait",
    base_font_size: 10,
    approval_strip: true,
    header: { subtitle: "", show_company_name: true, show_letter_box: false },
  };
}

type ServerElement = ElementProps & { id: number; type: typeof FORM_ELEMENT };

/**
 * Editable state from a server response. After a save, `previous` is the state
 * just sent: the response lists the elements in the same order, so each keeps
 * its React key (and the selection stays on it).
 */
export function fromResponse(response: ContentResponse, previous?: FormState): FormState {
  const server = response.sections as unknown as ServerElement[];
  const reuse = previous && previous.elements.length === server.length;
  return {
    version: response.version,
    footnote1: response.footnote1,
    footnote2: response.footnote2,
    settings: response.form_settings ?? defaultSettings(),
    elements: server.map((element, i) => {
      const { type: _type, ...props } = element;
      void _type;
      return { ...props, key: reuse ? previous.elements[i].key : newKey() } as FormElement;
    }),
  };
}

export interface FormSavePayload {
  base_version: number;
  footnote1: string;
  footnote2: string;
  form_settings: FormSettings;
  sections: Record<string, unknown>[];
}

/** The body of `PUT /documents/{id}/content/` for a form. */
export function toPayload(state: FormState): FormSavePayload {
  return {
    base_version: state.version,
    footnote1: state.footnote1,
    footnote2: state.footnote2,
    form_settings: state.settings,
    sections: state.elements.map(({ key: _key, id, ...props }) => {
      void _key;
      return { id: id ?? null, type: FORM_ELEMENT, ...props };
    }),
  };
}

export function snapshot(state: FormState): string {
  const { base_version: _version, ...rest } = toPayload(state);
  void _version;
  return JSON.stringify(rest);
}

/** Local checks that mirror the server's; the inputs already cap lengths and ranges. */
export function validate(state: FormState): string[] {
  const problems: string[] = [];
  if (state.elements.length > MAX_ELEMENTS) {
    problems.push(`یک فرم نمی‌تواند بیش از ${MAX_ELEMENTS.toLocaleString("fa-IR")} جزء داشته باشد.`);
  }
  state.elements.forEach((element, index) => {
    const where = `جزء ${(index + 1).toLocaleString("fa-IR")} (${elementLabel(element.kind)})`;
    if (element.kind === "table") {
      const total = element.columns.reduce((sum, column) => sum + column.width, 0);
      if (Math.abs(total - 100) > 0.5) problems.push(`${where}: مجموع پهنای ستون‌ها باید ۱۰۰ درصد باشد.`);
      if (element.rows.length + element.blank_rows > MAX_TABLE_ROWS) {
        problems.push(`${where}: یک جدول نمی‌تواند بیش از ${MAX_TABLE_ROWS.toLocaleString("fa-IR")} ردیف داشته باشد.`);
      }
    }
    if (element.kind === "fields") {
      element.rows.forEach((row, r) => {
        const total = row.cells.reduce((sum, cell) => sum + cell.width, 0);
        if (Math.abs(total - 100) > 0.5) {
          problems.push(`${where} — ردیف ${(r + 1).toLocaleString("fa-IR")}: مجموع پهنای خانه‌ها باید ۱۰۰ درصد باشد.`);
        }
      });
    }
  });
  return problems;
}

/** Moves the element at `from` so it ends up at index `to` (in the list without it). */
export function moveElement<T>(items: T[], from: number, to: number): T[] {
  if (from < 0 || from >= items.length) return items;
  const target = Math.max(0, Math.min(to, items.length - 1));
  if (target === from) return items;
  const next = items.slice();
  const [moved] = next.splice(from, 1);
  next.splice(target, 0, moved);
  return next;
}

/**
 * Where a dragged element lands when dropped on `over`, before or after it:
 * the index to pass to `moveElement`. Dropping an element on itself (either
 * half) leaves it where it is.
 */
export function dropIndex(from: number, over: number, after: boolean): number {
  const slot = after ? over + 1 : over; // insertion slot in the original list
  return slot > from ? slot - 1 : slot;
}

/** Inserts `element` after index `after` (-1 = at the start; past the end = at the end). */
export function insertAfter<T>(items: T[], element: T, after: number): T[] {
  const next = items.slice();
  next.splice(Math.min(after + 1, items.length), 0, element);
  return next;
}

/** «1. », «2.1. » for each numbered heading, keyed by element key — the same
 *  numbering the PDF prints (form_renderer._Numbering). */
export function headingNumbers(elements: FormElement[]): Map<string, string> {
  const counters = [0, 0, 0];
  const numbers = new Map<string, string>();
  for (const element of elements) {
    if (element.kind !== "heading" || !element.numbered || !element.text.trim()) continue;
    counters[element.level - 1] += 1;
    for (let deeper = element.level; deeper < 3; deeper += 1) counters[deeper] = 0;
    numbers.set(element.key, counters.slice(0, element.level).join(".") + ". ");
  }
  return numbers;
}

// ---------------------------------------------------------------------------
// Tables: column operations keep the header and rows in step with the columns
// ---------------------------------------------------------------------------

type TableShape = Pick<TableProps, "columns" | "header" | "rows" | "merges">;

export function addColumn<T extends TableShape>(table: T): T {
  if (table.columns.length >= MAX_COLUMNS) return table;
  const widths = widthsWithColumnAdded(table.columns.map((c) => c.width), MIN_COLUMN_WIDTH);
  return {
    ...table,
    columns: [...table.columns, { width: 0, align: "right", type: "text" } as TableColumn].map((c, i) => ({ ...c, width: widths[i] })),
    header: table.header.map((row) => [...row, ""]),
    rows: table.rows.map((row) => [...row, ""]),
  };
}

export function removeColumn<T extends TableShape>(table: T, index: number): T {
  if (table.columns.length <= 1) return table;
  const widths = widthsWithColumnRemoved(table.columns.map((c) => c.width), index);
  const drop = <X,>(row: X[]) => row.filter((_, i) => i !== index);
  return {
    ...table,
    columns: drop(table.columns).map((c, i) => ({ ...c, width: widths[i] })),
    header: table.header.map(drop),
    rows: table.rows.map(drop),
    merges: table.merges
      .map((m) => {
        if (index < m.col) return { ...m, col: m.col - 1 };
        if (index < m.col + m.colspan) return { ...m, colspan: m.colspan - 1 };
        return m;
      })
      .filter((m) => m.colspan > 0 && m.rowspan * m.colspan > 1),
  };
}

export function moveColumn<T extends TableShape>(table: T, from: number, to: number): T {
  if (to < 0 || to >= table.columns.length) return table;
  return {
    ...table,
    columns: moveElement(table.columns, from, to),
    header: table.header.map((row) => moveElement(row, from, to)),
    rows: table.rows.map((row) => moveElement(row, from, to)),
    // A merge touching either column would no longer be a rectangle: undo it.
    merges: table.merges.filter((m) => !touchesColumn(m, from) && !touchesColumn(m, to)),
  };
}

function touchesColumn(merge: Merge, column: number): boolean {
  return column >= merge.col && column < merge.col + merge.colspan;
}

export function setColumnWidths<T extends TableShape>(table: T, widths: number[]): T {
  return { ...table, columns: table.columns.map((c, i) => ({ ...c, width: widths[i] })) };
}

/** Replaces the text of one cell: `part` "header" or "rows", then row and column. */
export function setCell<T extends TableShape>(table: T, part: "header" | "rows", row: number, column: number, text: string): T {
  return {
    ...table,
    [part]: table[part].map((cells, r) => (r === row ? cells.map((cell, c) => (c === column ? text : cell)) : cells)),
  };
}

// ---------------------------------------------------------------------------
// Merged cells
// ---------------------------------------------------------------------------

export interface CellRange {
  top: number;
  left: number;
  bottom: number;
  right: number;
}

function rangeOf(merge: Merge): CellRange {
  return { top: merge.row, left: merge.col, bottom: merge.row + merge.rowspan - 1, right: merge.col + merge.colspan - 1 };
}

function intersects(a: CellRange, b: CellRange): boolean {
  return a.top <= b.bottom && b.top <= a.bottom && a.left <= b.right && b.left <= a.right;
}

/** The merge whose range contains the cell, if any. */
export function mergeAt(merges: Merge[], row: number, col: number): Merge | undefined {
  return merges.find((m) => row >= m.row && row < m.row + m.rowspan && col >= m.col && col < m.col + m.colspan);
}

/** Cells hidden under a merge (every cell of a merged range but its first), as "row,col". */
export function coveredCells(merges: Merge[]): Set<string> {
  const covered = new Set<string>();
  for (const m of merges) {
    for (let r = m.row; r < m.row + m.rowspan; r += 1) {
      for (let c = m.col; c < m.col + m.colspan; c += 1) {
        if (r !== m.row || c !== m.col) covered.add(`${r},${c}`);
      }
    }
  }
  return covered;
}

/**
 * Merges the cells from (r0, c0) to (r1, c1). The range grows to swallow any
 * merge it touches, keeps the first non-empty text (reading order) and clears
 * the rest. Returns the table unchanged — with a Persian reason — when the
 * range would join header and written rows, or is a single cell.
 */
export function mergeRange<T extends TableShape>(
  table: T,
  r0: number,
  c0: number,
  r1: number,
  c1: number,
): { table: T; error?: string } {
  const range: CellRange = {
    top: Math.min(r0, r1),
    bottom: Math.max(r0, r1),
    left: Math.min(c0, c1),
    right: Math.max(c0, c1),
  };
  // Grow until no merge sticks out of the range.
  for (let changed = true; changed; ) {
    changed = false;
    for (const m of table.merges) {
      const other = rangeOf(m);
      if (!intersects(range, other)) continue;
      const grown = {
        top: Math.min(range.top, other.top),
        bottom: Math.max(range.bottom, other.bottom),
        left: Math.min(range.left, other.left),
        right: Math.max(range.right, other.right),
      };
      if (grown.top !== range.top || grown.bottom !== range.bottom || grown.left !== range.left || grown.right !== range.right) {
        Object.assign(range, grown);
        changed = true;
      }
    }
  }
  const headerRows = table.header.length;
  if (range.top < headerRows && range.bottom >= headerRows) {
    return { table, error: "سرستون و ردیف‌های جدول را نمی‌توان با هم ادغام کرد." };
  }
  if (range.top === range.bottom && range.left === range.right) {
    return { table, error: "برای ادغام، دست‌کم دو خانه لازم است." };
  }

  const grid = [...table.header, ...table.rows].map((row) => row.slice());
  let text = "";
  for (let r = range.top; r <= range.bottom; r += 1) {
    for (let c = range.left; c <= range.right; c += 1) {
      if (!text && grid[r][c].trim()) text = grid[r][c];
      grid[r][c] = "";
    }
  }
  grid[range.top][range.left] = text;

  const merge: Merge = {
    row: range.top,
    col: range.left,
    rowspan: range.bottom - range.top + 1,
    colspan: range.right - range.left + 1,
  };
  return {
    table: {
      ...table,
      header: grid.slice(0, headerRows),
      rows: grid.slice(headerRows),
      merges: [...table.merges.filter((m) => !intersects(rangeOf(m), range)), merge],
    },
  };
}

/** Undoes the merge covering (row, col); the cells keep empty text. */
export function splitAt<T extends TableShape>(table: T, row: number, col: number): T {
  const merge = mergeAt(table.merges, row, col);
  if (!merge) return table;
  return { ...table, merges: table.merges.filter((m) => m !== merge) };
}

/** Merges the cell's range with the next column (towards the left on paper) or the next row. */
export function mergeNext<T extends TableShape>(table: T, row: number, col: number, direction: "col" | "row") {
  const current = mergeAt(table.merges, row, col);
  const range = current ? rangeOf(current) : { top: row, left: col, bottom: row, right: col };
  const gridRows = table.header.length + table.rows.length;
  if (direction === "col") {
    if (range.right + 1 >= table.columns.length) return { table, error: "ستونی بعد از این خانه نیست." };
    return mergeRange(table, range.top, range.left, range.bottom, range.right + 1);
  }
  if (range.bottom + 1 >= gridRows) return { table, error: "ردیف متن‌داری زیر این خانه نیست." };
  return mergeRange(table, range.top, range.left, range.bottom + 1, range.right);
}

/**
 * Changes the number of header rows (added or removed at the top) or of
 * written rows (at the bottom), moving or dropping merges to match.
 */
export function resizeRows<T extends TableShape>(table: T, part: "header" | "rows", count: number): T {
  const columns = table.columns.length;
  const blank = () => Array<string>(columns).fill("");
  if (part === "header") {
    const delta = count - table.header.length;
    const header =
      delta >= 0
        ? [...Array.from({ length: delta }, blank), ...table.header]
        : table.header.slice(-delta);
    const merges = table.merges
      .map((m) => ({ ...m, row: m.row + delta }))
      .filter((m) => m.row >= 0);
    return { ...table, header, merges };
  }
  const rows =
    count >= table.rows.length
      ? [...table.rows, ...Array.from({ length: count - table.rows.length }, blank)]
      : table.rows.slice(0, count);
  const last = table.header.length + count;
  return { ...table, rows, merges: table.merges.filter((m) => m.row + m.rowspan <= last) };
}
