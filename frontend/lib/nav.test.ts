import { describe, expect, it } from "vitest";
import { activeHref, hidesBottomNav, parseSidebarState } from "./nav";

const HREFS = ["/dashboard", "/inbox", "/documents", "/documents/history", "/quality", "/quality/audits", "/quality/risks"];

describe("activeHref", () => {
  it("matches an exact path", () => {
    expect(activeHref(HREFS, "/inbox")).toBe("/inbox");
  });

  it("prefers the most specific prefix", () => {
    expect(activeHref(HREFS, "/documents/history")).toBe("/documents/history");
    expect(activeHref(HREFS, "/documents/12/edit")).toBe("/documents");
    expect(activeHref(HREFS, "/quality/risks/4")).toBe("/quality/risks");
    expect(activeHref(HREFS, "/quality/9")).toBe("/quality");
  });

  it("never treats a longer word as a child", () => {
    expect(activeHref(HREFS, "/documentsx")).toBeUndefined();
  });

  it("matches the dashboard only by itself", () => {
    expect(activeHref(HREFS, "/dashboard")).toBe("/dashboard");
    expect(activeHref(["/dashboard"], "/dashboard/anything")).toBeUndefined();
  });
});

describe("hidesBottomNav", () => {
  it("on the designer and an open conversation only", () => {
    expect(hidesBottomNav("/documents/12/edit", null)).toBe(true);
    expect(hidesBottomNav("/documents/12/files/3", null)).toBe(false);
    expect(hidesBottomNav("/documents", null)).toBe(false);
    expect(hidesBottomNav("/inbox", new URLSearchParams("c=5"))).toBe(true);
    expect(hidesBottomNav("/inbox", new URLSearchParams("tab=awaiting"))).toBe(false);
    expect(hidesBottomNav("/dashboard", new URLSearchParams("c=5"))).toBe(false);
  });
});

describe("parseSidebarState", () => {
  it("is expanded unless it says collapsed", () => {
    expect(parseSidebarState("collapsed")).toBe("collapsed");
    expect(parseSidebarState(null)).toBe("expanded");
    expect(parseSidebarState("weird")).toBe("expanded");
  });
});
