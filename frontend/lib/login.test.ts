import { describe, expect, it } from "vitest";
import { DEFAULT_AFTER_LOGIN, loginRedirectUrl, normalizeDigits, normalizeNationalCode, safeNextPath } from "./login";

describe("safeNextPath", () => {
  it("keeps a plain in-app path, with its query and hash", () => {
    expect(safeNextPath("/documents")).toBe("/documents");
    expect(safeNextPath("/documents/12/edit")).toBe("/documents/12/edit");
    expect(safeNextPath("/projects?status=active#top")).toBe("/projects?status=active#top");
  });

  it("keeps the کارتابل's open conversation and tab (the ?next= proxy.ts now sends)", () => {
    expect(safeNextPath("/inbox?c=42")).toBe("/inbox?c=42");
    expect(safeNextPath("/inbox?tab=awaiting")).toBe("/inbox?tab=awaiting");
    // What the login page actually receives: proxy.ts sets it with searchParams, so it arrives encoded.
    const next = new URL("http://veye.invalid/login?next=" + encodeURIComponent("/inbox?c=42&tab=awaiting"));
    expect(safeNextPath(next.searchParams.get("next"))).toBe("/inbox?c=42&tab=awaiting");
  });

  it("a query string does not make an unsafe next safe", () => {
    for (const raw of ["//evil.example?c=42", "https://evil.example/inbox?c=42", "/\\evil.example?c=42", "/inbox?c=4\n2"]) {
      expect(safeNextPath(raw), raw).toBe(DEFAULT_AFTER_LOGIN);
    }
    expect(safeNextPath("/login?c=42")).toBe(DEFAULT_AFTER_LOGIN);
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
