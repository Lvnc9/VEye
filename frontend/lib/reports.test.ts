import { describe, expect, it } from "vitest";
import {
  documentsExportPath,
  formatDuration,
  formatPercent,
  kpiPath,
  projectsExportPath,
  workloadWidth,
  AGING_BUCKETS,
  agingWidth,
  qualityExportPath,
} from "./reports";

describe("documentsExportPath", () => {
  it("is the bare endpoint with no filters", () => {
    expect(documentsExportPath()).toBe("/reports/documents/export/");
    expect(documentsExportPath({ group: "", status: "  ", search: "" })).toBe("/reports/documents/export/");
  });

  it("carries only the filters that are set, trimmed and encoded", () => {
    expect(documentsExportPath({ group: "FORM", status: "UNDER_CONTROL" })).toBe(
      "/reports/documents/export/?group=FORM&status=UNDER_CONTROL",
    );
    // URLSearchParams writes a space as "+", which Django's query parser reads back as a space.
    expect(documentsExportPath({ search: " روش اجرایی " })).toBe(
      `/reports/documents/export/?search=${encodeURIComponent("روش").concat("+", encodeURIComponent("اجرایی"))}`,
    );
  });
});

describe("projectsExportPath", () => {
  it("asks for archived projects only when told to", () => {
    expect(projectsExportPath()).toBe("/reports/projects/export/");
    expect(projectsExportPath(true)).toBe("/reports/projects/export/?archived=1");
  });
});

describe("kpiPath", () => {
  it("passes the look-back window", () => {
    expect(kpiPath(90)).toBe("/reports/kpi/?days=90");
  });
});

describe("formatDuration", () => {
  it("says nothing was measured with a dash, never a zero", () => {
    expect(formatDuration(null)).toBe("—");
    expect(formatDuration(undefined)).toBe("—");
  });

  it("uses the unit a person would", () => {
    expect(formatDuration(0.01)).toBe("کمتر از یک ساعت");
    expect(formatDuration(0.25)).toBe("۶ ساعت");
    expect(formatDuration(1)).toBe("۱ روز");
    expect(formatDuration(3.36)).toBe("۳٫۴ روز");
    expect(formatDuration(10.07)).toBe("۱۰٫۱ روز");
  });

  it("does not round a day or more down into hours", () => {
    expect(formatDuration(0.99)).toBe("۲۴ ساعت");
    expect(formatDuration(1.04)).toBe("۱ روز");
  });
});

describe("formatPercent", () => {
  it("shows a Persian percentage, or a dash for nothing to measure", () => {
    expect(formatPercent(14.3)).toBe("۱۴٫۳٪");
    expect(formatPercent(0)).toBe("۰٪");
    expect(formatPercent(null)).toBe("—");
  });
});

describe("workloadWidth", () => {
  it("scales to the busiest person, and survives an empty list", () => {
    expect(workloadWidth(2, 4)).toBe(50);
    expect(workloadWidth(4, 4)).toBe(100);
    expect(workloadWidth(0, 0)).toBe(0);
  });
});


describe("the quality figures (Phase 18)", () => {
  it("exports the non-conformances with only the filters that are set", () => {
    expect(qualityExportPath()).toBe("/reports/quality/export/");
    expect(qualityExportPath({ status: "", severity: " ", source: "" })).toBe("/reports/quality/export/");
    expect(qualityExportPath({ status: "OPEN", severity: "CRITICAL" })).toBe("/reports/quality/export/?status=OPEN&severity=CRITICAL");
    expect(qualityExportPath({ source: "AUDIT" })).toBe("/reports/quality/export/?source=AUDIT");
  });

  it("names the server's four aging buckets, youngest first", () => {
    expect(AGING_BUCKETS.map(([key]) => key)).toEqual(["0_30", "31_60", "61_90", "over_90"]);
    expect(AGING_BUCKETS.map(([, label]) => label)).toEqual(["تا ۳۰ روز", "۳۱ تا ۶۰ روز", "۶۱ تا ۹۰ روز", "بیش از ۹۰ روز"]);
  });

  it("draws an aging bar against the fullest bucket", () => {
    const aging = { "0_30": 4, "31_60": 2, "61_90": 0, over_90: 1 };
    expect(agingWidth(aging, "0_30")).toBe(100);
    expect(agingWidth(aging, "31_60")).toBe(50);
    expect(agingWidth(aging, "61_90")).toBe(0);
    expect(agingWidth({ "0_30": 0, "31_60": 0, "61_90": 0, over_90: 0 }, "0_30")).toBe(0);
  });
});
