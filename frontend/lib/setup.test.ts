import { describe, expect, it } from "vitest";
import {
  EMPTY_ACCOUNT_FORM,
  PASSWORD_MIN_LENGTH,
  bootstrapBody,
  validateAccountForm,
  wizardStepFor,
  type AccountForm,
} from "./setup";
import type { SetupStatus } from "./types";

const status = (over: Partial<SetupStatus>): SetupStatus => ({
  developer_exists: true,
  company_exists: true,
  completed: false,
  step: "DOMAINS",
  has_root_lead: false,
  ...over,
});

describe("wizardStepFor", () => {
  it("asks an unauthenticated browser to sign in", () => {
    expect(wizardStepFor(status({ step: "UNITS" }), false)).toBe("login");
  });

  it("resumes at the bookmarked step for a signed-in developer", () => {
    expect(wizardStepFor(status({ step: "COMPANY" }), true)).toBe("company");
    expect(wizardStepFor(status({ step: "DOMAINS" }), true)).toBe("company");
    expect(wizardStepFor(status({ step: "UNITS" }), true)).toBe("units");
    expect(wizardStepFor(status({ step: "SECTIONS" }), true)).toBe("sections");
    expect(wizardStepFor(status({ step: "PEOPLE" }), true)).toBe("people"); // not "ready" (Phase 10)
  });

  it("is done when setup is complete, whoever is looking", () => {
    expect(wizardStepFor(status({ step: "DONE" }), true)).toBe("done");
    expect(wizardStepFor(status({ step: "DONE" }), false)).toBe("done");
  });
});

const filled = (over: Partial<AccountForm> = {}): AccountForm => ({
  ...EMPTY_ACCOUNT_FORM,
  fullName: " علی رضایی ",
  nationalCode: "۱۲۳ ۴۵",
  mobilePhone: " 0912 ",
  password: "Qz7-vector-maple-93",
  passwordConfirm: "Qz7-vector-maple-93",
  ...over,
});

describe("validateAccountForm", () => {
  it("accepts a complete form", () => {
    expect(validateAccountForm(filled())).toEqual({});
  });

  it("names every missing field, in Persian, next to the field", () => {
    const errors = validateAccountForm(EMPTY_ACCOUNT_FORM);
    expect(Object.keys(errors).sort()).toEqual(["fullName", "nationalCode", "password"]);
    expect(Object.values(errors).join(" ")).not.toMatch(/توکن/); // no setup token since 2026-09-25
  });

  it("has no company-name field at all (Phase 10: that moves to the wizard's own step)", () => {
    expect(EMPTY_ACCOUNT_FORM).not.toHaveProperty("companyName");
  });

  it("wants a password of a sane length that is typed twice", () => {
    expect(validateAccountForm(filled({ password: "abc", passwordConfirm: "abc" })).password).toContain(String(PASSWORD_MIN_LENGTH));
    expect(validateAccountForm(filled({ passwordConfirm: "other-one-1" })).passwordConfirm).toBeTruthy();
  });
});

describe("bootstrapBody", () => {
  it("trims, and normalises the national code to ASCII digits — no company name", () => {
    expect(bootstrapBody(filled())).toEqual({
      full_name: "علی رضایی",
      national_code: "12345",
      mobile_phone: "0912",
      password: "Qz7-vector-maple-93",
    });
  });
});
