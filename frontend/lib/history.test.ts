import { describe, expect, it } from "vitest";
import {
  ACTIVITY_WINDOWS,
  EMPTY_ACTIVITY_FILTERS,
  EMPTY_REVISION_FILTERS,
  EVENT_KIND_LABELS,
  activityParams,
  hasActiveFilters,
  revisionParams,
} from "./history";

describe("revisionParams", () => {
  it("sends only the filters that are set, and trims the search", () => {
    expect(revisionParams(EMPTY_REVISION_FILTERS, 1, 25)).toEqual({ page: 1, page_size: 25 });
    expect(
      revisionParams({ search: "  کنترل ", group: "PROCEDURE", status: "OBSOLETE", family: "PR-01" }, 3, 50),
    ).toEqual({ page: 3, page_size: 50, search: "کنترل", group: "PROCEDURE", status: "OBSOLETE", family: "PR-01" });
  });
});

describe("activityParams", () => {
  it("maps the window, kind and text filters", () => {
    expect(activityParams(EMPTY_ACTIVITY_FILTERS, 1, 25)).toEqual({ page: 1, page_size: 25 });
    expect(activityParams({ kind: "returned", days: "30", q: " PR-02 ", actor: "شجراوی " }, 2, 25)).toEqual({
      page: 2,
      page_size: 25,
      kind: "returned",
      days: "30",
      q: "PR-02",
      actor: "شجراوی",
    });
  });

  it("offers an all-time window first and only positive day counts", () => {
    expect(ACTIVITY_WINDOWS[0]).toEqual({ value: "", label: "همه زمان‌ها" });
    for (const w of ACTIVITY_WINDOWS.slice(1)) expect(Number(w.value)).toBeGreaterThan(0);
  });
});

describe("hasActiveFilters", () => {
  it("is false for the empty filters and true once anything is set", () => {
    expect(hasActiveFilters(EMPTY_REVISION_FILTERS)).toBe(false);
    expect(hasActiveFilters({ ...EMPTY_REVISION_FILTERS, family: "PR-01" })).toBe(true);
    expect(hasActiveFilters(EMPTY_ACTIVITY_FILTERS)).toBe(false);
    expect(hasActiveFilters({ ...EMPTY_ACTIVITY_FILTERS, days: "7" })).toBe(true);
  });
});

describe("EVENT_KIND_LABELS", () => {
  it("matches the server's Persian labels", () => {
    expect(EVENT_KIND_LABELS.returned).toBe("مرجوع شد");
    expect(Object.keys(EVENT_KIND_LABELS)).toEqual(["submitted", "confirmed", "approved", "returned", "superseded", "imported"]);
  });
});
