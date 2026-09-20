import { describe, expect, it } from "vitest";
import { MAX_SELECTED_IDS, bulkQuery, downloadUrl, preflightPath, selectionLabel } from "./bulk-print";

describe("bulkQuery", () => {
  it("sends the explicit ids when there are any", () => {
    expect(bulkQuery({ ids: [3, 1, 2] })).toBe("ids=3%2C1%2C2");
  });

  it("falls back to the non-empty filters when nothing is selected", () => {
    expect(bulkQuery({ ids: [] })).toBe("");
    expect(bulkQuery({ filters: { search: " کنترل ", group: "PROCEDURE", category: "", status: "" } })).toBe(
      "search=%DA%A9%D9%86%D8%AA%D8%B1%D9%84&group=PROCEDURE",
    );
    expect(bulkQuery({ filters: { search: "", group: "", category: "", status: "" } })).toBe("");
  });

  it("caps the ids at what the server accepts", () => {
    const many = Array.from({ length: MAX_SELECTED_IDS + 50 }, (_, i) => i + 1);
    expect(decodeURIComponent(bulkQuery({ ids: many })).split(",")).toHaveLength(MAX_SELECTED_IDS);
  });
});

describe("urls", () => {
  it("points the preflight and the download at the bulk-print routes", () => {
    expect(preflightPath({ ids: [1] })).toBe("/documents/bulk-print/preflight/?ids=1");
    expect(preflightPath({ ids: [] })).toBe("/documents/bulk-print/preflight/");
    expect(downloadUrl({ ids: [1, 2] })).toMatch(/\/documents\/bulk-print\/\?ids=1%2C2$/);
    expect(downloadUrl({ filters: { status: "UNDER_CONTROL" } })).toMatch(/\/documents\/bulk-print\/\?status=UNDER_CONTROL$/);
  });
});

describe("selectionLabel", () => {
  it("says what a click would print", () => {
    expect(selectionLabel(3, true)).toBe("3 مستند انتخاب‌شده");
    expect(selectionLabel(0, true)).toBe("همهٔ نتایج فیلتر");
    expect(selectionLabel(0, false)).toBe("همهٔ مستندات");
  });
});
