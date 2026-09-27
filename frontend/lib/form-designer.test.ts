import { describe, expect, it } from "vitest";
import {
  addColumn,
  dragToDelta,
  moveColumn,
  removeColumn,
  setCell,
  widthsWithColumnAdded,
  widthsWithColumnRemoved,
  ELEMENT_KINDS,
  FORM_ELEMENT,
  MAX_ELEMENTS,
  defaultSettings,
  dropIndex,
  evenWidths,
  fromResponse,
  headingNumbers,
  insertAfter,
  moveBoundary,
  moveElement,
  newElement,
  setWidth,
  snapshot,
  toPayload,
  validate,
  type FormElement,
  type FormState,
} from "./form-designer";
import type { ContentResponse, DocumentRow } from "./types";

function response(sections: unknown[], extra: Partial<ContentResponse> = {}): ContentResponse {
  return {
    document: {} as DocumentRow,
    version: 3,
    editable: true,
    logo_url: null,
    footnote1: "بالا",
    footnote2: "پایین",
    body_kind: "form",
    form_settings: { ...defaultSettings(), orientation: "landscape" },
    previous_changes: [],
    sections,
    ...extra,
  } as unknown as ContentResponse;
}

const heading = (text: string, level: 1 | 2 | 3 = 1, numbered = true): FormElement => ({
  ...newElement("heading"),
  text,
  level,
  numbered,
} as FormElement);

describe("newElement", () => {
  it("gives every palette kind its server defaults", () => {
    for (const { kind } of ELEMENT_KINDS) {
      const element = newElement(kind);
      expect(element.kind).toBe(kind);
      expect(element.key).toMatch(/^s\d+$/);
    }
    expect(newElement("divider")).toMatchObject({ style: "solid", thickness: 0.75, space_before: 2, space_after: 2 });
    expect(newElement("spacer")).toMatchObject({ height: 5 });
  });

  it("gives fresh keys", () => {
    expect(newElement("text").key).not.toBe(newElement("text").key);
  });
});

describe("fromResponse / toPayload", () => {
  const server = [
    { id: 7, type: FORM_ELEMENT, kind: "heading", text: "مشخصات", style: "band", level: 1, numbered: true, align: "right" },
    { id: 8, type: FORM_ELEMENT, kind: "spacer", height: 10 },
  ];

  it("round-trips", () => {
    const state = fromResponse(response(server));
    expect(state.version).toBe(3);
    expect(state.settings.orientation).toBe("landscape");
    expect(state.elements.map((e) => e.kind)).toEqual(["heading", "spacer"]);
    const payload = toPayload(state);
    expect(payload.base_version).toBe(3);
    expect(payload.form_settings.orientation).toBe("landscape");
    expect(payload.sections).toEqual(server.map((s) => ({ ...s })));
    // The client key never travels.
    expect(JSON.stringify(payload)).not.toMatch(/"key"/);
  });

  it("keeps keys across a save when the element count matches", () => {
    const before = fromResponse(response(server));
    const after = fromResponse(response(server), before);
    expect(after.elements.map((e) => e.key)).toEqual(before.elements.map((e) => e.key));
  });

  it("uses default settings when the server sends none", () => {
    expect(fromResponse(response([], { form_settings: null })).settings).toEqual(defaultSettings());
  });

  it("sends a new element with a null id", () => {
    const state: FormState = { ...fromResponse(response([])), elements: [newElement("page_break")] };
    expect(toPayload(state).sections).toEqual([{ id: null, type: FORM_ELEMENT, kind: "page_break" }]);
  });

  it("snapshot ignores the version but sees an edit", () => {
    const state = fromResponse(response(server));
    expect(snapshot({ ...state, version: 99 })).toBe(snapshot(state));
    const edited = { ...state, settings: { ...state.settings, base_font_size: 12 } };
    expect(snapshot(edited)).not.toBe(snapshot(state));
  });
});

describe("validate", () => {
  it("caps the number of elements", () => {
    const state = fromResponse(response([]));
    expect(validate({ ...state, elements: Array.from({ length: MAX_ELEMENTS }, () => newElement("spacer")) })).toEqual([]);
    expect(validate({ ...state, elements: Array.from({ length: MAX_ELEMENTS + 1 }, () => newElement("spacer")) })).toHaveLength(1);
  });
});

describe("reordering", () => {
  const list = ["a", "b", "c", "d"];

  it("moves an item to an index", () => {
    expect(moveElement(list, 0, 2)).toEqual(["b", "c", "a", "d"]);
    expect(moveElement(list, 3, 0)).toEqual(["d", "a", "b", "c"]);
    expect(moveElement(list, 1, 1)).toBe(list);
    expect(moveElement(list, 1, 99)).toEqual(["a", "c", "d", "b"]);
    expect(moveElement(list, 7, 0)).toBe(list);
  });

  it("turns a drop before/after a row into the right index", () => {
    const drop = (from: number, over: number, after: boolean) => moveElement(list, from, dropIndex(from, over, after));
    expect(drop(0, 2, false)).toEqual(["b", "a", "c", "d"]); // a before c
    expect(drop(0, 2, true)).toEqual(["b", "c", "a", "d"]); // a after c
    expect(drop(3, 0, false)).toEqual(["d", "a", "b", "c"]); // d before a
    expect(drop(3, 1, true)).toEqual(["a", "b", "d", "c"]); // d after b
    expect(drop(2, 2, false)).toEqual(list); // onto itself
    expect(drop(2, 2, true)).toEqual(list);
    expect(drop(1, 0, true)).toEqual(list); // b after a: where it already is
  });

  it("inserts after an index, at the start, or at the end", () => {
    expect(insertAfter(list, "x", 1)).toEqual(["a", "b", "x", "c", "d"]);
    expect(insertAfter(list, "x", -1)).toEqual(["x", "a", "b", "c", "d"]);
    expect(insertAfter(list, "x", 10)).toEqual(["a", "b", "c", "d", "x"]);
  });
});

describe("headingNumbers", () => {
  it("numbers like the PDF: by level, resetting deeper levels", () => {
    const elements = [
      heading("الف"),
      heading("الف-۱", 2),
      heading("الف-۲", 2),
      heading("بدون شماره", 1, false),
      heading("ب"),
      heading("ب-۱", 2),
      heading("ب-۱-۱", 3),
      heading("   "), // empty: not printed, not counted
      heading("ج"),
    ];
    const numbers = headingNumbers(elements);
    expect(elements.map((e) => numbers.get(e.key) ?? null)).toEqual([
      "1. ",
      "1.1. ",
      "1.2. ",
      null,
      "2. ",
      "2.1. ",
      "2.1.1. ",
      null,
      "3. ",
    ]);
  });
});

describe("widths", () => {
  const sum = (widths: number[]) => Math.round(widths.reduce((a, b) => a + b, 0) * 10) / 10;

  it("evens a row out to exactly 100", () => {
    for (const n of [1, 2, 3, 6, 7]) expect(sum(evenWidths(n))).toBe(100);
    expect(evenWidths(3)).toEqual([33.3, 33.3, 33.4]);
    expect(evenWidths(0)).toEqual([]);
  });

  it("moves a border without changing the total", () => {
    expect(moveBoundary([50, 50], 0, 10, 5)).toEqual([60, 40]);
    expect(moveBoundary([50, 50], 0, -10, 5)).toEqual([40, 60]);
    expect(moveBoundary([20, 30, 50], 1, 5, 5)).toEqual([20, 35, 45]);
  });

  it("never squeezes a cell below the minimum", () => {
    expect(moveBoundary([50, 50], 0, 60, 5)).toEqual([95, 5]);
    expect(moveBoundary([50, 50], 0, -60, 5)).toEqual([5, 95]);
  });

  it("ignores a border that does not exist", () => {
    const widths = [50, 50];
    expect(moveBoundary(widths, 1, 5, 5)).toBe(widths);
    expect(moveBoundary(widths, -1, 5, 5)).toBe(widths);
  });

  it("sets one width, taking the difference from the next cell (or the previous for the last)", () => {
    expect(setWidth([25, 25, 50], 0, 40, 5)).toEqual([40, 10, 50]);
    expect(setWidth([25, 25, 50], 2, 60, 5)).toEqual([25, 15, 60]);
    expect(setWidth([100], 0, 50, 5)).toEqual([100]);
    expect(sum(setWidth([33.3, 33.3, 33.4], 1, 50, 5))).toBe(100);
  });

  it("validate reports a row that does not add up", () => {
    const state = fromResponse(response([]));
    const fields = newElement("fields");
    if (fields.kind !== "fields") throw new Error("unreachable");
    expect(validate({ ...state, elements: [fields] })).toEqual([]);
    const broken = { ...fields, rows: [{ cells: [{ ...fields.rows[0].cells[0], width: 30 }] }] };
    expect(validate({ ...state, elements: [broken] })).toHaveLength(1);
  });
});

describe("tables", () => {
  const table = () => {
    const element = newElement("table");
    if (element.kind !== "table") throw new Error("unreachable");
    return { ...element, rows: [["", "کارشناسی", "تهران"]] };
  };

  it("drags a border in RTL: moving it left widens the column on its right", () => {
    expect(dragToDelta(-50, 500)).toBe(10);
    expect(dragToDelta(50, 500)).toBe(-10);
    expect(dragToDelta(10, 0)).toBe(0);
  });

  it("adds a column taking half of the widest one", () => {
    expect(widthsWithColumnAdded([10, 60, 30], 4)).toEqual([10, 30, 30, 30]);
    expect(widthsWithColumnAdded([], 4)).toEqual([100]);
    expect(widthsWithColumnAdded([5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 6, 4], 4)).toHaveLength(21);
  });

  it("gives a removed column's width to its neighbour", () => {
    expect(widthsWithColumnRemoved([10, 60, 30], 0)).toEqual([70, 30]);
    expect(widthsWithColumnRemoved([10, 60, 30], 2)).toEqual([10, 90]);
    expect(widthsWithColumnRemoved([100], 0)).toEqual([100]);
  });

  it("keeps header and rows in step when columns are added, removed or moved", () => {
    const added = addColumn(table());
    expect(added.columns).toHaveLength(4);
    expect(added.header[0]).toEqual(["ردیف", "عنوان", "توضیحات", ""]);
    expect(added.rows[0]).toEqual(["", "کارشناسی", "تهران", ""]);
    expect(added.columns.reduce((sum, c) => sum + c.width, 0)).toBe(100);

    const removed = removeColumn(table(), 1);
    expect(removed.header[0]).toEqual(["ردیف", "توضیحات"]);
    expect(removed.rows[0]).toEqual(["", "تهران"]);
    expect(removed.columns.map((c) => c.width)).toEqual([10, 90]);

    const moved = moveColumn(table(), 2, 1);
    expect(moved.header[0]).toEqual(["ردیف", "توضیحات", "عنوان"]);
    expect(moved.rows[0]).toEqual(["", "تهران", "کارشناسی"]);
    expect(moved.columns.map((c) => c.width)).toEqual([10, 30, 60]);
    const unchanged = table();
    expect(moveColumn(unchanged, 0, -1)).toBe(unchanged); // no column left of the edge
  });

  it("edits one cell", () => {
    const edited = setCell(table(), "rows", 0, 2, "شیراز");
    expect(edited.rows[0]).toEqual(["", "کارشناسی", "شیراز"]);
    expect(setCell(table(), "header", 0, 0, "#").header[0][0]).toBe("#");
  });

  it("validate reports columns that do not add up", () => {
    const state = fromResponse(response([]));
    const broken = { ...table(), columns: table().columns.map((c) => ({ ...c, width: 10 })) };
    expect(validate({ ...state, elements: [table()] })).toEqual([]);
    expect(validate({ ...state, elements: [broken] })).toHaveLength(1);
  });
});
