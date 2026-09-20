import { afterEach, describe, expect, it, vi } from "vitest";
import { setFlash, takeFlash } from "./flash";

function fakeWindow(storage: Partial<Storage>) {
  vi.stubGlobal("window", { sessionStorage: storage });
}

afterEach(() => vi.unstubAllGlobals());

describe("flash message", () => {
  it("is read exactly once", () => {
    const data = new Map<string, string>();
    fakeWindow({
      setItem: (k, v) => void data.set(k, v),
      getItem: (k) => data.get(k) ?? null,
      removeItem: (k) => void data.delete(k),
    });
    setFlash("مستند PR-01-01 ذخیره شد.");
    expect(takeFlash()).toBe("مستند PR-01-01 ذخیره شد.");
    expect(takeFlash()).toBeNull();
  });

  it("returns null when nothing was set", () => {
    fakeWindow({ getItem: () => null, removeItem: () => undefined });
    expect(takeFlash()).toBeNull();
  });

  it("never throws when storage is blocked", () => {
    const blocked = () => {
      throw new DOMException("blocked", "SecurityError");
    };
    fakeWindow({ setItem: blocked, getItem: blocked, removeItem: blocked });
    expect(() => setFlash("x")).not.toThrow();
    expect(takeFlash()).toBeNull();
  });
});
