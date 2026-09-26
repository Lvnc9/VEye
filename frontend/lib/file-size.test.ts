import { describe, expect, it } from "vitest";
import { formatSize } from "./file-size";

describe("formatSize", () => {
  it("picks the unit by size", () => {
    expect(formatSize(0)).toBe("0 B");
    expect(formatSize(1023)).toBe("1023 B");
    expect(formatSize(1024)).toBe("1 KB");
    expect(formatSize(1024 * 1024 - 1)).toBe("1024 KB");
    expect(formatSize(20 * 1024 * 1024)).toBe("20.0 MB");
  });
});
