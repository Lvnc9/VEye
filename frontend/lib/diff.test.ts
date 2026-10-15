import { describe, expect, it } from "vitest";
import { blocksOf, changeCount, diffBlocks, diffContents, diffWords, lcsPairs, toBlock, type Block } from "./diff";
import type { ServerSection } from "./types";

const short = (...lines: string[]) => ({ type: "Short Explanation", lines }) as ServerSection;
const block = (type: string, ...lines: string[]): Block => ({ type, label: type, lines });

describe("lcsPairs", () => {
  it("finds the longest run of matches in order", () => {
    expect(lcsPairs(["a", "b", "c", "d"], ["a", "c", "d", "e"], (x, y) => x === y)).toEqual([
      [0, 0],
      [2, 1],
      [3, 2],
    ]);
    expect(lcsPairs([], ["a"], (x, y) => x === y)).toEqual([]);
  });
});

describe("diffWords", () => {
  it("marks removed words on the old side and added words on the new side", () => {
    const { oldTokens, newTokens } = diffWords("ثبت درخواست در سامانه", "ثبت سریع درخواست در پرتال");
    expect(oldTokens.filter((t) => t.op === "del").map((t) => t.text.trim())).toEqual(["سامانه"]);
    expect(oldTokens.map((t) => t.text).join("")).toBe("ثبت درخواست در سامانه");
    expect(newTokens.filter((t) => t.op === "add").map((t) => t.text.trim())).toEqual(["سریع", "پرتال"]);
    expect(newTokens.map((t) => t.text).join("")).toBe("ثبت سریع درخواست در پرتال");
  });

  it("keeps identical text as one same token", () => {
    expect(diffWords("یک دو", "یک دو")).toEqual({
      oldTokens: [{ op: "same", text: "یک دو" }],
      newTokens: [{ op: "same", text: "یک دو" }],
    });
  });
});

describe("diffBlocks", () => {
  it("keeps unchanged blocks, pairs an edited one, and reports additions and removals", () => {
    const old = [block("A", "x"), block("B", "y"), block("C", "z")];
    const now = [block("A", "x"), block("B", "y2"), block("D", "w")];
    const rows = diffBlocks(old, now);
    expect(rows.map((row) => row.kind)).toEqual(["same", "changed", "added", "removed"]);
    expect(changeCount(rows)).toBe(3);
  });

  it("survives a reorder without calling everything changed", () => {
    const a = block("A", "1");
    const b = block("B", "2");
    const rows = diffBlocks([a, b], [b, a]);
    expect(rows.filter((row) => row.kind === "same")).toHaveLength(1);
    expect(rows.map((row) => row.kind).sort()).toEqual(["added", "removed", "same"]);
  });
});

describe("blocksOf / toBlock", () => {
  it("reads every block type and the footnotes", () => {
    const blocks = blocksOf({
      sections: [
        short("بند یک", ""),
        { type: "Long Explanation", heading: "هدف", body: "متن اول\nمتن دوم", extra_boxes: [], rich: null, files: [] } as ServerSection,
        {
          type: "Responsibilities",
          rows: [{ domain: 1, unit: 2, domain_name: "IT", unit_name: "توسعه", text: "اجرا" }],
        } as ServerSection,
        { type: "Attachment", items: [{ caption: "فرم", document: { id: 1, full_code: "FR-01-01", title: "", status: "UNDER_CONTROL", status_label: "" } }] } as ServerSection,
      ],
      footnote1: "پاورقی",
      footnote2: "",
    });
    expect(blocks.map((b) => b.label)).toEqual(["تشریحی کوتاه", "تشریحی بلند", "مسئولیت ها", "ضمائم", "پاورقی"]);
    expect(blocks[0].lines).toEqual(["بند یک"]);
    expect(blocks[1].lines).toEqual(["هدف", "متن اول", "متن دوم"]);
    expect(blocks[2].lines).toEqual(["IT › توسعه: اجرا"]);
    expect(blocks[3].lines).toEqual(["FR-01-01 — فرم"]);
  });

  it("summarises a form element by its strings, labelled by its kind", () => {
    const b = toBlock({ type: "Form Element", kind: "heading", text: "مشخصات", style: "band", level: 1 });
    expect(b.label).toBe("عنوان بخش");
    expect(b.lines).toEqual(["مشخصات"]);
  });
});

describe("diffContents", () => {
  it("compares two payloads end to end", () => {
    const rows = diffContents(
      { sections: [short("الف"), short("ب")], footnote1: "", footnote2: "" },
      { sections: [short("الف"), short("ب تازه")], footnote1: "", footnote2: "" },
    );
    expect(rows.map((row) => row.kind)).toEqual(["same", "changed"]);
  });
});
