import { describe, expect, it } from "vitest";
import { DEFAULT_AFTER_LOGIN, loginRedirectUrl, normalizeDigits, normalizeNationalCode, safeNextPath } from "./login";

describe("safeNextPath", () => {
  it("keeps a plain in-app path, with its query and hash", () => {
    expect(safeNextPath("/documents")).toBe("/documents");
    expect(safeNextPath("/documents/12/edit")).toBe("/documents/12/edit");
    expect(safeNextPath("/projects?status=active#top")).toBe("/projects?status=active#top");
  });

  it("falls back to the dashboard when there is nothing, or it is not a path", () => {
    for (const raw of [null, undefined, "", "dashboard", "documents", "?next=/x"]) {
      expect(safeNextPath(raw)).toBe(DEFAULT_AFTER_LOGIN);
    }
  });

  it("refuses anything that could leave the site", () => {
    for (const raw of [
      "//evil.example",
      "//evil.example/path",
      "https://evil.example",
      "http://evil.example/x",
      "javascript:alert(1)",
      "/\\evil.example",
      "/\\/evil.example",
      "/ok\n//evil.example",
      "/ok\t",
      "/" + String.fromCharCode(0) + "x",
    ]) {
      expect(safeNextPath(raw), raw).toBe(DEFAULT_AFTER_LOGIN);
    }
  });

  it("never returns to the login page itself", () => {
    expect(safeNextPath("/login")).toBe(DEFAULT_AFTER_LOGIN);
    expect(safeNextPath("/login?next=/documents")).toBe(DEFAULT_AFTER_LOGIN);
  });
});

describe("national code typing", () => {
  it("turns Persian and Arabic-Indic digits into ASCII", () => {
    expect(normalizeDigits("۱۲۳۴۵۶۷۸۹۰")).toBe("1234567890");
    expect(normalizeDigits("٠١٢٣٤٥٦٧٨٩")).toBe("0123456789");
    expect(normalizeDigits("کد ۱۲")).toBe("کد 12");
  });

  it("drops whitespace, so a pasted code with spaces still matches", () => {
    expect(normalizeNationalCode(" ۱۲۳ ۴۵ 67 ")).toBe("1234567");
    expect(normalizeNationalCode("9000000001")).toBe("9000000001");
  });
});

describe("loginRedirectUrl", () => {
  it("remembers where a dead session was, so signing in returns there", () => {
    expect(loginRedirectUrl("/documents/12/edit")).toBe("/login?next=%2Fdocuments%2F12%2Fedit");
    expect(loginRedirectUrl("/projects", "?status=active")).toBe("/login?next=%2Fprojects%3Fstatus%3Dactive");
  });

  it("does not loop, and does not bother for the default landing page", () => {
    expect(loginRedirectUrl("/login")).toBe("/login");
    expect(loginRedirectUrl("/login/extra")).toBe("/login");
    expect(loginRedirectUrl("/dashboard")).toBe("/login");
  });
});
