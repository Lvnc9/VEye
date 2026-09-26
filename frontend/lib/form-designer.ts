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
  | SignaturesProps;
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
