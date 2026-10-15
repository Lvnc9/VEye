import { describe, expect, it } from "vitest";
import { EMPTY_PASSWORD_FORM, passwordErrors, passwordFormProblem } from "./password";

describe("passwordFormProblem", () => {
  const filled = {
    current: "old-secret-1",
    next: "new-secret-22",
    repeat: "new-secret-22",
  };

  it("accepts a complete form", () => {
    expect(passwordFormProblem(filled)).toBeNull();
  });

  it("asks for the current password first", () => {
    expect(passwordFormProblem(EMPTY_PASSWORD_FORM)).toContain("فعلی");
  });

  it("refuses a short new password", () => {
    expect(passwordFormProblem({ ...filled, next: "short", repeat: "short" })).toContain("۸");
  });

  it("refuses a repeat that does not match", () => {
    expect(passwordFormProblem({ ...filled, repeat: "new-secret-23" })).toContain("تکرار");
  });
});

describe("passwordErrors", () => {
  it("puts each field's messages under that field", () => {
    expect(passwordErrors({ current_password: ["رمز عبور فعلی درست نیست."] })).toEqual({
      current: "رمز عبور فعلی درست نیست.",
    });
    expect(passwordErrors({ new_password: ["خیلی کوتاه است.", "خیلی رایج است."] })).toEqual({
      next: "خیلی کوتاه است. خیلی رایج است.",
    });
  });

  it("falls back to a general message", () => {
    expect(passwordErrors({ detail: "زیاد تلاش کردید." })).toEqual({
      other: "زیاد تلاش کردید.",
    });
    expect(passwordErrors(undefined)).toEqual({
      other: "تغییر رمز انجام نشد.",
    });
  });
});
