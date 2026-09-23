import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { proxy } from "./proxy";

function nextParam(url: string): string | null {
  const response = proxy(new NextRequest(url));
  const location = response.headers.get("location");
  expect(location, url).not.toBeNull();
  return new URL(location!).searchParams.get("next");
}

describe("proxy", () => {
  it("sends an anonymous visitor to /login, remembering the page with its query", () => {
    expect(nextParam("http://veye.test/inbox?c=42")).toBe("/inbox?c=42");
    expect(nextParam("http://veye.test/inbox?tab=awaiting")).toBe("/inbox?tab=awaiting");
    expect(nextParam("http://veye.test/documents/12/edit")).toBe("/documents/12/edit");
  });

  it("does not add next for the root", () => {
    const response = proxy(new NextRequest("http://veye.test/"));
    expect(response.headers.get("location")).toBe("http://veye.test/login");
  });

  it("lets a signed-in visitor and the public pages through", () => {
    const signedIn = new NextRequest("http://veye.test/inbox?c=42", { headers: { cookie: "refresh_token=x" } });
    expect(proxy(signedIn).headers.get("location")).toBeNull();
    for (const url of ["http://veye.test/login?next=/inbox", "http://veye.test/setup", "http://veye.test/verify/abc"]) {
      expect(proxy(new NextRequest(url)).headers.get("location"), url).toBeNull();
    }
  });
});
