import { describe, expect, it } from "vitest";
import {
  ROLE_ORDER,
  canAddSection,
  fromResponse,
  moveSection,
  newSection,
  snapshot,
  toPayload,
  validate,
  type DesignerState,
} from "./designer";
import type { ContentResponse, DesignerSection, DocumentRow } from "./types";

function state(sections: DesignerSection[], version = 3): DesignerState {
  return { version, footnote1: "پاورقی ۱", footnote2: "پاورقی ۲", sections };
}

describe("newSection", () => {
  it("gives each block the starting shape V_1.0 did", () => {
    const short = newSection("Short Explanation");
    expect(short.type === "Short Explanation" && short.lines).toEqual(["", ""]);

    const resp = newSection("Responsibilities");
    expect(resp.type === "Responsibilities" && resp.roles.map((r) => r.role)).toEqual(ROLE_ORDER);
    expect(resp.type === "Responsibilities" && resp.notes).toEqual([]);
  });

  it("does not seed a Changes Table with V_1.0's hardcoded demo rows", () => {
    const table = newSection("Changes Table");
    expect(table.type === "Changes Table" && table.rows).toEqual([]);
  });

  it("gives every block a distinct key", () => {
    const keys = new Set([1, 2, 3, 4, 5].map(() => newSection("Short Explanation").key));
    expect(keys.size).toBe(5);
  });
});

describe("toPayload", () => {
  it("sends the version the editor loaded, plus footnotes", () => {
    const payload = toPayload(state([]));
    expect(payload).toEqual({ base_version: 3, footnote1: "پاورقی ۱", footnote2: "پاورقی ۲", sections: [] });
  });

  it("maps a Long block's files to ids", () => {
    const long = newSection("Long Explanation");
    if (long.type !== "Long Explanation") throw new Error();
    long.files = [
      { id: 7, name: "a.pdf", kind: "DOCUMENT", kind_label: "فایل", size: 1, download_url: "x" },
      { id: 9, name: "b.png", kind: "PICTURE", kind_label: "تصویر", size: 1, download_url: "y" },
    ];
    const [section] = toPayload(state([long])).sections;
    expect(section.file_ids).toEqual([7, 9]);
    expect(section).not.toHaveProperty("files");
  });

  it("never sends a change row's date — the server owns it", () => {
    const table = newSection("Changes Table");
    if (table.type !== "Changes Table") throw new Error();
    table.rows = [{ id: 4, text: "الف", date: "2026-01-01" }, { text: "ب" }];
    const [section] = toPayload(state([table])).sections;
    expect(section.rows).toEqual([
      { id: 4, text: "الف" },
      { id: null, text: "ب" },
    ]);
  });

  it("sends attachments as caption + document id", () => {
    const attachment = newSection("Attachment");
    if (attachment.type !== "Attachment") throw new Error();
    attachment.items = [
      { caption: "فرم", document: { id: 12, full_code: "FR-01-01", title: "t", status: "DRAFT", status_label: "پیش نویس" } },
    ];
    const [section] = toPayload(state([attachment])).sections;
    expect(section.items).toEqual([{ caption: "فرم", document_id: 12 }]);
  });

  it("carries a saved block's id, and null for a new one", () => {
    const saved = { ...newSection("Short Explanation"), id: 42 };
    const fresh = newSection("Short Explanation");
    const sections = toPayload(state([saved, fresh])).sections;
    expect(sections[0].id).toBe(42);
    expect(sections[1].id).toBeNull();
  });

  it("preserves the order of the blocks", () => {
    const a = newSection("Short Explanation");
    const b = newSection("Long Explanation");
    expect(toPayload(state([b, a])).sections.map((s) => s.type)).toEqual(["Long Explanation", "Short Explanation"]);
  });
});

describe("fromResponse", () => {
  it("round-trips through toPayload", () => {
    const response = {
      document: {} as DocumentRow,
      version: 5,
      editable: true,
      logo_url: null,
      footnote1: "الف",
      footnote2: "ب",
      previous_changes: [],
      sections: [
        { id: 1, type: "Short Explanation", lines: ["۱-هدف", ""] },
        { id: 2, type: "Changes Table", rows: [{ id: 3, text: "تغییر", date: "2026-02-03" }] },
      ],
    } as ContentResponse;

    const restored = fromResponse(response);
    expect(restored.version).toBe(5);
    const payload = toPayload(restored);
    expect(payload.sections[0]).toEqual({ id: 1, type: "Short Explanation", lines: ["۱-هدف", ""] });
    expect(payload.sections[1]).toEqual({ id: 2, type: "Changes Table", rows: [{ id: 3, text: "تغییر" }] });
  });
});

describe("fromResponse — keys across a save", () => {
  const response = {
    document: {} as DocumentRow,
    version: 2,
    editable: true,
    logo_url: null,
    footnote1: "",
    footnote2: "",
    previous_changes: [],
    sections: [
      { id: 10, type: "Short Explanation", lines: [""] },
      { id: 11, type: "Long Explanation", heading: "", body: "", extra_boxes: [], files: [] },
    ],
  } as ContentResponse;

  it("keeps each block's key when given the sections that were just saved", () => {
    const before = [newSection("Short Explanation"), newSection("Long Explanation")];
    const after = fromResponse(response, before);
    expect(after.sections.map((s) => s.key)).toEqual(before.map((s) => s.key));
    expect(after.sections.map((s) => s.id)).toEqual([10, 11]);
  });

  it("mints fresh keys on a plain load, and distinct ones", () => {
    const keys = fromResponse(response).sections.map((s) => s.key);
    expect(new Set(keys).size).toBe(2);
  });

  it("does not reuse keys if the block count changed", () => {
    const stale = [newSection("Short Explanation")];
    const after = fromResponse(response, stale);
    expect(after.sections.map((s) => s.key)).not.toContain(stale[0].key);
  });
});

describe("snapshot", () => {
  it("is unaffected by the version, which only moves on a save", () => {
    const sections = [newSection("Short Explanation")];
    expect(snapshot(state(sections, 1))).toBe(snapshot(state(sections, 9)));
  });

  it("changes when content changes", () => {
    const section = newSection("Short Explanation");
    const before = snapshot(state([section]));
    if (section.type !== "Short Explanation") throw new Error();
    const after = snapshot(state([{ ...section, lines: ["تغییر", ""] }]));
    expect(after).not.toBe(before);
  });

  it("changes when blocks are reordered", () => {
    const a = newSection("Short Explanation");
    const b = newSection("Long Explanation");
    expect(snapshot(state([a, b]))).not.toBe(snapshot(state([b, a])));
  });
});

describe("moveSection", () => {
  const [a, b, c] = ["Short Explanation", "Long Explanation", "Attachment"].map((t) =>
    newSection(t as DesignerSection["type"]),
  );

  it("moves a block up and down", () => {
    expect(moveSection([a, b, c], 1, -1)).toEqual([b, a, c]);
    expect(moveSection([a, b, c], 1, 1)).toEqual([a, c, b]);
  });

  it("does nothing past either end, and never mutates its input", () => {
    const original = [a, b, c];
    expect(moveSection(original, 0, -1)).toBe(original);
    expect(moveSection(original, 2, 1)).toBe(original);
    moveSection(original, 0, 1);
    expect(original).toEqual([a, b, c]);
  });
});

describe("canAddSection", () => {
  it("allows any number of text blocks but only one Responsibilities / Changes Table", () => {
    const sections = [newSection("Short Explanation"), newSection("Responsibilities")];
    expect(canAddSection(sections, "Short Explanation")).toBe(true);
    expect(canAddSection(sections, "Long Explanation")).toBe(true);
    expect(canAddSection(sections, "Attachment")).toBe(true);
    expect(canAddSection(sections, "Responsibilities")).toBe(false);
    expect(canAddSection(sections, "Changes Table")).toBe(true);
  });
});

describe("validate", () => {
  it("accepts a well-formed document", () => {
    expect(validate(state([newSection("Short Explanation"), newSection("Attachment")]))).toEqual([]);
  });

  it("flags an attachment with no caption or no document", () => {
    const attachment = newSection("Attachment");
    if (attachment.type !== "Attachment") throw new Error();
    attachment.items = [{ caption: "", document: null }];
    const problems = validate(state([newSection("Short Explanation"), attachment]));
    expect(problems).toHaveLength(2);
    expect(problems.join(" ")).toContain("بخش 2");
  });

  it("flags a blank change row", () => {
    const table = newSection("Changes Table");
    if (table.type !== "Changes Table") throw new Error();
    table.rows = [{ text: "  " }];
    expect(validate(state([table]))).toHaveLength(1);
  });
});
