import { describe, expect, it } from "vitest";
import { coverageLabel, unreadCount, type Coverage } from "./distribution";

describe("coverageLabel", () => {
  it("counts in Persian with a rounded percentage", () => {
    expect(coverageLabel(3, 8)).toBe("۳ از ۸ نفر (۳۸٪)");
    expect(coverageLabel(0, 4)).toBe("۰ از ۴ نفر (۰٪)");
  });

  it("is a dash when nobody was asked", () => {
    expect(coverageLabel(0, 0)).toBe("—");
    expect(coverageLabel(null, null)).toBe("—");
  });
});

describe("unreadCount", () => {
  it("is everyone asked minus those who read it", () => {
    const coverage: Coverage = { document: { id: 1, full_code: "PR-01-01", title: "x" }, total: 5, acknowledged: 2, percent: 40, groups: [] };
    expect(unreadCount(coverage)).toBe(3);
  });
});
