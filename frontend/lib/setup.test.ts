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

const status = (over: Partial<SetupStatus>): SetupStatus => ({ needed: false, has_users: true, step: "DOMAINS", ...over });

describe("wizardStepFor", () => {
  it("starts at the account on a fresh database, signed in or not", () => {
    expect(wizardStepFor(status({ needed: true, step: null }), false)).toBe("account");
    expect(wizardStepFor(status({ needed: true, step: null, has_users: false }), true)).toBe("account");
  });

  it("asks an unauthenticated browser to sign in once a company exists", () => {
    expect(wizardStepFor(status({ step: "UNITS" }), false)).toBe("login");
  });

  it("resumes at the bookmarked step for a signed-in manager", () => {
    expect(wizardStepFor(status({ step: "COMPANY" }), true)).toBe("company");
    expect(wizardStepFor(status({ step: "DOMAINS" }), true)).toBe("company");
    expect(wizardStepFor(status({ step: "UNITS" }), true)).toBe("units");
    expect(wizardStepFor(status({ step: "SECTIONS" }), true)).toBe("sections");
    expect(wizardStepFor(status({ step: "PEOPLE" }), true)).toBe("ready");
  });

  it("is done when setup is complete, whoever is looking", () => {
    expect(wizardStepFor(status({ step: "DONE" }), true)).toBe("done");
    expect(wizardStepFor(status({ step: "DONE" }), false)).toBe("done");
  });
});

const filled = (over: Partial<AccountForm> = {}): AccountForm => ({
  ...EMPTY_ACCOUNT_FORM,
  companyName: " شرکت ",
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
    expect(Object.keys(errors).sort()).toEqual(["companyName", "fullName", "nationalCode", "password"]);
    expect(Object.values(errors).join(" ")).not.toMatch(/توکن/); // no setup token since 2026-09-25
  });

  it("wants a password of a sane length that is typed twice", () => {
    expect(validateAccountForm(filled({ password: "abc", passwordConfirm: "abc" })).password).toContain(String(PASSWORD_MIN_LENGTH));
    expect(validateAccountForm(filled({ passwordConfirm: "other-one-1" })).passwordConfirm).toBeTruthy();
  });
});

describe("bootstrapBody", () => {
  it("trims, and normalises the national code to ASCII digits", () => {
    expect(bootstrapBody(filled())).toEqual({
      company_name: "شرکت",
      manager: { full_name: "علی رضایی", national_code: "12345", mobile_phone: "0912", password: "Qz7-vector-maple-93" },
    });
  });
});
