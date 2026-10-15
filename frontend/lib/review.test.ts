import { describe, expect, it } from "vitest";
import { intervalChoices, reviewIntervalLabel } from "./review";

describe("reviewIntervalLabel", () => {
  it("speaks in years when it can", () => {
    expect(reviewIntervalLabel(12)).toBe("هر سال");
    expect(reviewIntervalLabel(24)).toBe("هر ۲ سال");
    expect(reviewIntervalLabel(6)).toBe("هر ۶ ماه");
    expect(reviewIntervalLabel(18)).toBe("هر ۱۸ ماه");
    expect(reviewIntervalLabel(0)).toBe("بدون بازنگری دوره‌ای");
  });
});

describe("intervalChoices", () => {
  it("keeps an unusual stored value among the choices, in order", () => {
    expect(intervalChoices(12)).toEqual([0, 3, 6, 12, 18, 24, 36]);
    expect(intervalChoices(9)).toEqual([0, 3, 6, 9, 12, 18, 24, 36]);
  });
});
