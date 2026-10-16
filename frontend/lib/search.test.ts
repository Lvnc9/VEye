import { describe, expect, it } from "vitest";
import { flattenResults, isPaletteShortcut, moveActive, searchable, type SearchGroup } from "./search";

const groups: SearchGroup[] = [
  { type: "documents", label: "مستندات", items: [{ id: 1, title: "الف", subtitle: "", url: "/documents/1/edit" }, { id: 2, title: "ب", subtitle: "", url: "/documents/2/edit" }] },
  { type: "risks", label: "ریسک‌ها", items: [{ id: 1, title: "ج", subtitle: "", url: "/quality/risks/1" }] },
];

describe("searchable", () => {
  it("needs two letters after trimming", () => {
    expect(searchable("")).toBe(false);
    expect(searchable(" ک ")).toBe(false);
    expect(searchable("کی")).toBe(true);
  });
});

describe("flattenResults", () => {
  it("lists every hit in order with its group and a key unique across groups", () => {
    const flat = flattenResults(groups);
    expect(flat.map((r) => r.title)).toEqual(["الف", "ب", "ج"]);
    expect(flat.map((r) => r.group)).toEqual(["مستندات", "مستندات", "ریسک‌ها"]);
    expect(new Set(flat.map((r) => r.key)).size).toBe(3); // both id 1s differ by group
  });
});

describe("moveActive", () => {
  it("starts at the first or last, then wraps", () => {
    expect(moveActive(-1, 1, 3)).toBe(0);
    expect(moveActive(-1, -1, 3)).toBe(2);
    expect(moveActive(2, 1, 3)).toBe(0);
    expect(moveActive(0, -1, 3)).toBe(2);
    expect(moveActive(1, 1, 3)).toBe(2);
  });

  it("highlights nothing when there is nothing", () => {
    expect(moveActive(0, 1, 0)).toBe(-1);
  });
});

describe("isPaletteShortcut", () => {
  const key = (over: Partial<Parameters<typeof isPaletteShortcut>[0]>) => ({ key: "k", metaKey: false, ctrlKey: false, altKey: false, ...over });
  it("is ⌘K or Ctrl+K, in either case", () => {
    expect(isPaletteShortcut(key({ metaKey: true }))).toBe(true);
    expect(isPaletteShortcut(key({ ctrlKey: true, key: "K" }))).toBe(true);
  });
  it("is not a bare k, another letter, or Alt-modified", () => {
    expect(isPaletteShortcut(key({}))).toBe(false);
    expect(isPaletteShortcut(key({ metaKey: true, key: "j" }))).toBe(false);
    expect(isPaletteShortcut(key({ metaKey: true, altKey: true }))).toBe(false);
  });
});
