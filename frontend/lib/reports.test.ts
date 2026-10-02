import { describe, expect, it } from "vitest";
import { documentsExportPath, projectsExportPath } from "./reports";

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
