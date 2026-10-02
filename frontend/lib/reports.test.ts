import { describe, expect, it } from "vitest";
import { documentsExportPath, formatDuration, formatPercent, kpiPath, projectsExportPath, workloadWidth } from "./reports";

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
