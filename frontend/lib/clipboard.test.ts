import { afterEach, describe, expect, it, vi } from "vitest";
import { copyText } from "./clipboard";

afterEach(() => vi.unstubAllGlobals());

describe("copyText", () => {
  it("uses the async clipboard when there is one", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    expect(await copyText("http://x/y")).toBe(true);
    expect(writeText).toHaveBeenCalledWith("http://x/y");
  });

  it("falls back to a textarea and execCommand when the clipboard is missing or refuses", async () => {
    const field = { value: "", style: {}, setAttribute: vi.fn(), select: vi.fn(), remove: vi.fn() };
    const document = {
      createElement: vi.fn(() => field),
      body: { appendChild: vi.fn() },
      execCommand: vi.fn(() => true),
      activeElement: null,
    };
    vi.stubGlobal("document", document);
    vi.stubGlobal("navigator", { clipboard: { writeText: vi.fn().mockRejectedValue(new Error("denied")) } });
    expect(await copyText("link")).toBe(true);
    expect(field.value).toBe("link");
    expect(document.execCommand).toHaveBeenCalledWith("copy");
    expect(field.remove).toHaveBeenCalled();

    vi.stubGlobal("navigator", {});
    document.execCommand.mockReturnValue(false);
    expect(await copyText("link")).toBe(false);
  });
});
