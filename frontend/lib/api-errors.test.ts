import { describe, expect, it } from "vitest";
import { extractErrorMessage, flattenErrorMessages } from "./api-errors";

describe("extractErrorMessage", () => {
  it("prefers the server's detail", () => {
    expect(extractErrorMessage({ detail: "راه‌اندازی اولیه قبلاً انجام شده است.", code: "x" }, 403)).toBe(
      "راه‌اندازی اولیه قبلاً انجام شده است.",
    );
  });

  it("joins DRF field errors", () => {
    expect(extractErrorMessage({ title: ["الف"], group: ["ب"] }, 400)).toBe("الف ب");
  });

  it("reads errors nested inside a nested serializer (the setup wizard's password rules)", () => {
    const body = { manager: { password: ["رمز عبور کوتاه است.", "رمز عبور رایج است."], full_name: ["الزامی است."] } };
    expect(extractErrorMessage(body, 400)).toBe("رمز عبور کوتاه است. رمز عبور رایج است. الزامی است.");
  });

  it("never shows a machine code, and falls back to a Persian generic message", () => {
    expect(flattenErrorMessages({ code: "node_not_empty", children: 2, detail: "پیام" })).toEqual(["پیام"]);
    expect(extractErrorMessage({ code: "conflict", count: 3 }, 409)).toBe("درخواست ناموفق بود (کد 409).");
    expect(extractErrorMessage(undefined, 500)).toBe("درخواست ناموفق بود (کد 500).");
  });
});
