import { describe, expect, it } from "vitest";
import {
  emptyRich,
  fontSizeFromCss,
  isAllowedLink,
  legacyToRich,
  paletteColor,
  parseTableSize,
  richText,
  snapFontSize,
} from "./rich-doc";

describe("legacyToRich", () => {
  it("makes a paragraph of every line and turns markers into marks", () => {
    const rich = legacyToRich("خط **پررنگ** و ~~کج~~ و --زیرخط--\nدوم", []);
    expect(rich.v).toBe(1);
    const [first, second] = rich.doc.content;
    expect(first.content).toEqual([
      { type: "text", text: "خط " },
      { type: "text", text: "پررنگ", marks: [{ type: "bold" }] },
      { type: "text", text: " و " },
      { type: "text", text: "کج", marks: [{ type: "italic" }] },
      { type: "text", text: " و " },
      { type: "text", text: "زیرخط", marks: [{ type: "underline" }] },
    ]);
    expect(second.content).toEqual([{ type: "text", text: "دوم" }]);
  });

  it("keeps blank lines as blank paragraphs", () => {
    const rich = legacyToRich("الف\n\nب", []);
    expect(rich.doc.content.map((p) => p.content?.[0]?.text ?? "")).toEqual(["الف", "", "ب"]);
    expect(rich.doc.content[1]).toEqual({ type: "paragraph" });
  });

  it("appends each extra box after a blank line, as the PDF printed them", () => {
    expect(richText(legacyToRich("بدنه", ["کادر یک", "  ", "کادر دو"]))).toBe("بدنه\n\nکادر یک\n\nکادر دو");
  });

  it("an empty body with a box starts with the box, and nothing at all is one empty paragraph", () => {
    expect(richText(legacyToRich("", ["فقط کادر"]))).toBe("فقط کادر");
    expect(legacyToRich("", [])).toEqual(emptyRich());
  });

  it("accepts CRLF from a browser textarea", () => {
    expect(legacyToRich("الف\r\nب", []).doc.content).toHaveLength(2);
  });
});

describe("what the editor may offer", () => {
  it("snaps a size to the nearest one the printer knows", () => {
    expect(snapFontSize(13.4)).toBe(14);
    expect(snapFontSize(5)).toBe(8);
    expect(snapFontSize(99)).toBe(32);
    expect(snapFontSize(12)).toBe(12);
  });

  it("reads css sizes in pt and px", () => {
    expect(fontSizeFromCss("14pt")).toBe(14);
    expect(fontSizeFromCss("16px")).toBe(12);
    expect(fontSizeFromCss("18.6667px")).toBe(14);
    expect(fontSizeFromCss("large")).toBeNull();
    expect(fontSizeFromCss(null)).toBeNull();
  });

  it("keeps only palette colours, however they are written", () => {
    expect(paletteColor("#DC2626")).toBe("#dc2626");
    expect(paletteColor("rgb(220, 38, 38)")).toBe("#dc2626");
    expect(paletteColor("rgba(29,78,216,1)")).toBe("#1d4ed8");
    expect(paletteColor("#123456")).toBeNull();
    expect(paletteColor("red")).toBeNull();
    expect(paletteColor("")).toBeNull();
  });

  it("allows only http, https and mailto links, like the server", () => {
    for (const ok of ["http://localhost:3000/documents/1/files/2", "https://a.b/c?d=e", "mailto:a@b.co"]) {
      expect(isAllowedLink(ok)).toBe(true);
    }
    for (const bad of ["javascript:alert(1)", "ftp://x", "//x", "http://a b", "", "data:text/html,x"]) {
      expect(isAllowedLink(bad)).toBe(false);
    }
  });
});

describe("parseTableSize (the custom table dialog)", () => {
  it("accepts whole numbers in range, Persian digits included", () => {
    expect(parseTableSize("3", "4")).toEqual({ ok: true, rows: 3, columns: 4 });
    expect(parseTableSize("۱۲", " ۵ ")).toEqual({ ok: true, rows: 12, columns: 5 });
    expect(parseTableSize("200", "20")).toEqual({ ok: true, rows: 200, columns: 20 });
    expect(parseTableSize("1", "1")).toEqual({ ok: true, rows: 1, columns: 1 });
  });

  it("names the field that is out of range, in Persian", () => {
    expect(parseTableSize("201", "3")).toEqual({ ok: false, rows: "تعداد سطر باید بین ۱ تا ۲۰۰ باشد.", columns: null });
    expect(parseTableSize("3", "21")).toEqual({ ok: false, rows: null, columns: "تعداد ستون باید بین ۱ تا ۲۰ باشد." });
    expect(parseTableSize("0", "0")).toMatchObject({ ok: false, rows: expect.any(String), columns: expect.any(String) });
  });

  it("refuses anything that is not a whole number", () => {
    for (const text of ["", "  ", "2.5", "-1", "abc", "1e2", "٣.٥"]) {
      expect(parseTableSize(text, "3")).toMatchObject({ ok: false, rows: "تعداد سطر را با عدد بنویسید." });
    }
  });
});
