import { afterEach, describe, expect, it, vi } from "vitest";
import { apiGetIfSignedIn } from "./api-client";

function respond(status: number, body?: unknown) {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiGetIfSignedIn", () => {
  it("answers null for a visitor with no session, without sending them to /login", async () => {
    const location = { href: "http://veye.test/setup", pathname: "/setup", search: "" };
    vi.stubGlobal("window", { location });
    const fetch = vi.fn(async () => respond(401, { detail: "no session" }));
    vi.stubGlobal("fetch", fetch);

    expect(await apiGetIfSignedIn("/auth/me/")).toBeNull();
    expect(location.href).toBe("http://veye.test/setup");
    expect(fetch.mock.calls.map((call) => String((call as unknown[])[0]))).toEqual([
      expect.stringContaining("/auth/me/"),
      expect.stringContaining("/auth/refresh/"),
    ]);
  });

  it("uses the silent refresh like every other request", async () => {
    const answers = [respond(401), respond(200), respond(200, { id: 7 })];
    vi.stubGlobal("fetch", vi.fn(async () => answers.shift()!));
    expect(await apiGetIfSignedIn("/auth/me/")).toEqual({ id: 7 });
  });

  it("still throws other errors", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => respond(500, { detail: "خطا" })));
    await expect(apiGetIfSignedIn("/auth/me/")).rejects.toMatchObject({ status: 500 });
  });
});
