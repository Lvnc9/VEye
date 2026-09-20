import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchVerification } from "./verify";

function respond(status: number, body: unknown) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(body), { status })));
}

afterEach(() => vi.unstubAllGlobals());

describe("fetchVerification", () => {
  it("returns the verdict without credentials or caching", async () => {
    respond(200, { found: true, state: "valid", full_code: "PR-01-01" });
    const outcome = await fetchVerification("PR-01-01");
    expect(outcome).toEqual({ kind: "ok", data: { found: true, state: "valid", full_code: "PR-01-01" } });

    const [url, init] = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(String(url)).toMatch(/\/verify\/PR-01-01\/$/);
    expect(init).toMatchObject({ cache: "no-store", credentials: "omit" });
  });

  it("escapes the code it puts in the URL", async () => {
    respond(404, { found: false });
    await fetchVerification("../admin");
    const [url] = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(String(url)).toContain("/verify/..%2Fadmin/");
  });

  it("reports an unknown code with the server's Persian message", async () => {
    respond(404, { found: false, detail: "مستندی با این کد یافت نشد." });
    expect(await fetchVerification("XX-01-01")).toEqual({ kind: "not_found", message: "مستندی با این کد یافت نشد." });
  });

  it("does not treat a rate limit or a server error as 'not found'", async () => {
    respond(403, {});
    expect((await fetchVerification("PR-01-01")).kind).toBe("error");
    respond(500, {});
    expect((await fetchVerification("PR-01-01")).kind).toBe("error");
  });

  it("survives the network being down", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("offline"))));
    const outcome = await fetchVerification("PR-01-01");
    expect(outcome.kind).toBe("error");
  });
});
