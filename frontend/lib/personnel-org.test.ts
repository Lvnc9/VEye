import { describe, expect, it } from "vitest";
import {
  EMPTY_ASSIGNMENT,
  UNASSIGNED_PATH,
  hasAssignment,
  membershipBody,
  registerOutcome,
  type AssignmentForm,
} from "./personnel-org";

describe("assignment", () => {
  it("is optional: an empty form places nobody", () => {
    expect(hasAssignment(EMPTY_ASSIGNMENT)).toBe(false);
    expect(hasAssignment({ ...EMPTY_ASSIGNMENT, nodeId: 7 })).toBe(true);
  });

  it("builds the membership request, trimming the label and sending no 'primary' choice", () => {
    const form = { nodeId: 7, isLead: true, positionLabel: "  رئیس فروش " } as AssignmentForm & { nodeId: number };
    expect(membershipBody(42, form)).toEqual({ user: 42, node: 7, is_lead: true, position_label: "رئیس فروش" });
    expect(Object.keys(membershipBody(42, form))).not.toContain("is_primary"); // the server makes their first one primary
  });

  it("does not make someone مسئول unless asked", () => {
    expect(membershipBody(1, { nodeId: 3, isLead: false, positionLabel: "" }).is_lead).toBe(false);
  });
});

describe("registerOutcome", () => {
  it("says a person was placed, by node name", () => {
    expect(registerOutcome("بخش فروش", null)).toEqual({
      tone: "success",
      message: "پروفایل پرسنل با موفقیت ثبت شد و در «بخش فروش» قرار گرفت.",
    });
  });

  it("is a plain success when nobody was placed", () => {
    expect(registerOutcome(null, null)).toEqual({ tone: "success", message: "پروفایل پرسنل با موفقیت ثبت شد." });
  });

  it("never reads a failed placement as a failed registration, nor hides it", () => {
    const outcome = registerOutcome("بخش فروش", "گره بایگانی شده است.");
    expect(outcome.tone).toBe("partial");
    expect(outcome.message).toContain("ثبت شد");
    expect(outcome.message).toContain("گره بایگانی شده است.");
    expect(outcome.message).toContain("ساختار سازمان");
  });
});

describe("the unassigned list", () => {
  it("asks the people directory for those with no membership", () => {
    expect(UNASSIGNED_PATH).toContain("unassigned=1");
  });
});
