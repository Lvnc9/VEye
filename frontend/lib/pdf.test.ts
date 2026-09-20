import { describe, expect, it, vi } from "vitest";
import { ApiError } from "./api-client";
import { MESSAGES, PdfBuildError, officialPdfAction, waitForPdf } from "./pdf";
import type { PdfState, PdfStatus } from "./types";

function state(status: PdfStatus, extra: Partial<PdfState> = {}): PdfState {
  return {
    kind: "official",
    status,
    status_label: "",
    requested_at: null,
    built_at: null,
    size: null,
    error: "",
    stale: false,
    download_url: null,
    ...extra,
  };
}

/** A clock that only moves when `sleep` is called. */
function fakeClock() {
  let t = 0;
  return { now: () => t, sleep: async (ms: number) => void (t += ms) };
}

describe("officialPdfAction", () => {
  it("builds when there is no PDF yet and offers a retry after a failure", () => {
    expect(officialPdfAction("none")).toEqual({ mode: "build", label: "ساخت PDF" });
    expect(officialPdfAction("failed")).toEqual({ mode: "build", label: "ساخت مجدد PDF" });
  });

  it("is busy while building and prints once ready", () => {
    expect(officialPdfAction("building").mode).toBe("busy");
    expect(officialPdfAction("ready")).toEqual({ mode: "open", label: "چاپ" });
  });
});

describe("waitForPdf", () => {
  it("polls until the build leaves 'building'", async () => {
    const clock = fakeClock();
    const read = vi
      .fn<() => Promise<PdfState>>()
      .mockResolvedValueOnce(state("building"))
      .mockResolvedValueOnce(state("building"))
      .mockResolvedValueOnce(state("ready", { download_url: "http://x/d" }));
    const result = await waitForPdf(read, { ...clock, intervalMs: 500 });
    expect(result.status).toBe("ready");
    expect(read).toHaveBeenCalledTimes(3);
    expect(clock.now()).toBe(1000); // two sleeps of 500 ms
  });

  it("returns a failed build for the caller to report", async () => {
    const read = async () => state("failed", { error: "خطا" });
    expect((await waitForPdf(read, fakeClock())).status).toBe("failed");
  });

  it("gives up at the deadline with a Persian message", async () => {
    const read = vi.fn(async () => state("building"));
    await expect(waitForPdf(read, { ...fakeClock(), intervalMs: 1000, timeoutMs: 3000 })).rejects.toThrow(
      MESSAGES.timeout,
    );
    // Polled at t = 0, 1000, 2000, 3000 and then stopped.
    expect(read).toHaveBeenCalledTimes(4);
  });

  it("propagates request errors instead of polling forever", async () => {
    const read = async () => {
      throw new ApiError("ارتباط با سرور برقرار نشد.", 0);
    };
    await expect(waitForPdf(read, fakeClock())).rejects.toBeInstanceOf(ApiError);
  });
});

describe("PdfBuildError", () => {
  it("is distinguishable from an ApiError", () => {
    expect(new PdfBuildError("x")).not.toBeInstanceOf(ApiError);
  });
});
