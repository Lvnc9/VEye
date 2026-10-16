import { describe, expect, it } from "vitest";
import {
  LEAVE_STATUS_LABELS,
  LEAVE_STATUS_TONE,
  LEAVE_TYPE_LABELS,
  emptyLeaveForm,
  inclusiveDays,
  leavePayload,
  leaveQueryParams,
  leaveTabs,
  balanceWarningText,
  balanceYears,
  parseEntitlement,
  signedDays,
  validateLeaveForm,
  workingDaysText,
} from "./leave";

describe("the leave vocabulary", () => {
  it("covers every type and status the server can send, each with a tone", () => {
    expect(Object.keys(LEAVE_TYPE_LABELS)).toEqual(["ANNUAL", "SICK", "UNPAID"]);
    expect(Object.keys(LEAVE_STATUS_LABELS)).toEqual(["PENDING", "APPROVED", "REJECTED", "CANCELLED"]);
    expect(Object.keys(LEAVE_STATUS_TONE)).toEqual(Object.keys(LEAVE_STATUS_LABELS));
  });
});

describe("inclusiveDays", () => {
  it("counts both ends, across a month and a year", () => {
    expect(inclusiveDays("2026-10-08", "2026-10-08")).toBe(1);
    expect(inclusiveDays("2026-10-08", "2026-10-10")).toBe(3);
    expect(inclusiveDays("2026-10-30", "2026-11-02")).toBe(4);
    expect(inclusiveDays("2026-12-31", "2027-01-01")).toBe(2);
  });

  it("is null for a missing date or an end before the start", () => {
    expect(inclusiveDays("", "2026-10-08")).toBeNull();
    expect(inclusiveDays("2026-10-08", "")).toBeNull();
    expect(inclusiveDays("2026-10-09", "2026-10-08")).toBeNull();
  });
});

describe("leaveTabs — who gets which tab", () => {
  it("gives everyone their own requests", () => {
    expect(leaveTabs({ leads: false, top: false, hr: false })).toEqual(["mine"]);
  });

  it("adds «to decide» for a مسئول or the مدیر عامل, and «all» for HR or the مدیر عامل — HR decides nothing", () => {
    expect(leaveTabs({ leads: true, top: false, hr: false })).toEqual(["mine", "decide"]);
    expect(leaveTabs({ leads: false, top: false, hr: true })).toEqual(["mine", "all", "balances"]);
    expect(leaveTabs({ leads: false, top: true, hr: true })).toEqual(["mine", "decide", "all", "balances"]);
  });
});

describe("leaveQueryParams", () => {
  it("asks for the tab's slice and only a status that is set", () => {
    expect(leaveQueryParams("mine", "", 1, 20)).toEqual({ page: 1, page_size: 20, mine: 1 });
    expect(leaveQueryParams("decide", "", 2, 20)).toEqual({ page: 2, page_size: 20, to_decide: 1 });
    expect(leaveQueryParams("all", "APPROVED", 1, 20)).toEqual({ page: 1, page_size: 20, status: "APPROVED" });
  });
});

describe("the request form", () => {
  it("starts on an annual leave with no dates", () => {
    expect(emptyLeaveForm()).toEqual({ leave_type: "ANNUAL", starts_on: "", ends_on: "", reason: "" });
  });

  it("asks for both days in order, in Persian", () => {
    const ok = { leave_type: "SICK" as const, starts_on: "2026-10-08", ends_on: "2026-10-09", reason: "" };
    expect(validateLeaveForm(ok)).toEqual({});
    expect(Object.keys(validateLeaveForm(emptyLeaveForm())).sort()).toEqual(["ends_on", "starts_on"]);
    expect(validateLeaveForm({ ...ok, ends_on: "2026-10-07" }).ends_on).toBeTruthy();
    expect(validateLeaveForm({ ...ok, reason: "x".repeat(2001) }).reason).toContain("۲۰۰۰");
  });

  it("sends the trimmed reason", () => {
    expect(leavePayload({ leave_type: "ANNUAL", starts_on: "2026-10-08", ends_on: "2026-10-09", reason: "  سفر  " })).toEqual({
      leave_type: "ANNUAL",
      starts_on: "2026-10-08",
      ends_on: "2026-10-09",
      reason: "سفر",
    });
  });
});


describe("working days and balances (Phase 22)", () => {
  it("says working days, and the calendar days only when they differ", () => {
    expect(workingDaysText(3, 5)).toBe("۳ روز کاری (از ۵ روز)");
    expect(workingDaysText(2, 2)).toBe("۲ روز کاری");
  });

  it("phrases the decider's warning, never showing a negative remainder there", () => {
    expect(balanceWarningText({ year: 1405, requested: 3, remaining: 2 })).toBe("۳ روز درخواست، ۲ روز مانده در ۱۴۰۵");
    expect(balanceWarningText({ year: 1405, requested: 3, remaining: -1 })).toBe("۳ روز درخواست، ۰ روز مانده در ۱۴۰۵");
  });

  it("signs an overdrawn balance", () => {
    expect(signedDays(-2)).toBe("−۲");
    expect(signedDays(4)).toBe("۴");
  });
});

describe("balances list helpers (Phase 22)", () => {
  it("offers the years from now back to the start year", () => {
    expect(balanceYears(1404, 1406)).toEqual([1406, 1405, 1404]);
    expect(balanceYears(1406, 1406)).toEqual([1406]);
    expect(balanceYears(1408, 1406)).toEqual([1406]); // a start year in the future: just this year
  });

  it("reads an entitlement, an empty box clearing it", () => {
    expect(parseEntitlement("30")).toBe(30);
    expect(parseEntitlement("  ")).toBeNull();
    expect(parseEntitlement("-1")).toBe("invalid");
    expect(parseEntitlement("121")).toBe("invalid");
    expect(parseEntitlement("abc")).toBe("invalid");
  });
});
