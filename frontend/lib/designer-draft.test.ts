import { describe, expect, it } from "vitest";
import { clearDraft, draftStorageKey, findRecovery, readDraft, writeDraft } from "./designer-draft";

function memoryStore() {
  const data = new Map<string, string>();
  return {
    data,
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => void data.set(key, value),
    removeItem: (key: string) => void data.delete(key),
  };
}

type S = { version: number; text: string };
const snapshot = (state: S) => state.text;

describe("designer drafts", () => {
  it("round-trips per user and document", () => {
    const store = memoryStore();
    writeDraft<S>({ userId: 1, documentId: 9, baseVersion: 3, state: { version: 3, text: "x" }, at: 5 }, store);
    expect(store.data.has(draftStorageKey(1, 9))).toBe(true);
    expect(readDraft<S>(1, 9, store)?.state.text).toBe("x");
    expect(readDraft<S>(2, 9, store)).toBeNull(); // another user on the same browser
    clearDraft(1, 9, store);
    expect(readDraft<S>(1, 9, store)).toBeNull();
  });

  it("offers a draft made on the same version that differs from the server", () => {
    const store = memoryStore();
    writeDraft<S>({ userId: 1, documentId: 9, baseVersion: 3, state: { version: 3, text: "edited" }, at: 42 }, store);
    expect(findRecovery<S>(1, 9, 3, "saved", snapshot, store)).toEqual({ kind: "offer", state: { version: 3, text: "edited" }, at: 42 });
    expect(store.data.size).toBe(1); // kept until the author decides
  });

  it("reports a draft from another version as stale, without offering it", () => {
    const store = memoryStore();
    writeDraft<S>({ userId: 1, documentId: 9, baseVersion: 2, state: { version: 2, text: "old" }, at: 7 }, store);
    expect(findRecovery<S>(1, 9, 3, "saved", snapshot, store)).toEqual({ kind: "stale", at: 7 });
  });

  it("offers nothing for a draft that matches what is saved", () => {
    const store = memoryStore();
    writeDraft<S>({ userId: 1, documentId: 9, baseVersion: 3, state: { version: 3, text: "saved" }, at: 7 }, store);
    expect(findRecovery<S>(1, 9, 3, "saved", snapshot, store)).toBeNull();
  });

  it("is a pure read: it never changes storage", () => {
    const store = memoryStore();
    writeDraft<S>({ userId: 1, documentId: 9, baseVersion: 2, state: { version: 2, text: "old" }, at: 7 }, store);
    findRecovery<S>(1, 9, 3, "saved", snapshot, store);
    findRecovery<S>(1, 9, 2, "old", snapshot, store);
    expect(store.data.size).toBe(1);
  });

  it("survives broken or missing storage", () => {
    const broken = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("full");
      },
      removeItem: () => {
        throw new Error("blocked");
      },
    };
    expect(() => writeDraft<S>({ userId: 1, documentId: 1, baseVersion: 1, state: { version: 1, text: "" }, at: 1 }, broken)).not.toThrow();
    expect(findRecovery<S>(1, 1, 1, "", snapshot, broken)).toBeNull();
    const garbage = memoryStore();
    garbage.setItem(draftStorageKey(1, 1), "{not json");
    expect(readDraft<S>(1, 1, garbage)).toBeNull();
    expect(findRecovery<S>(1, 1, 1, "", snapshot, null)).toBeNull();
  });
});
