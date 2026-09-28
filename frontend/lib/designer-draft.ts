/**
 * Unsaved designer work kept in this browser (Phase 12), so a closed tab or a
 * crash does not lose it: the designer writes its state here while it is dirty
 * and offers «بازیابی» when the document is opened again.
 *
 * Only this browser, only a convenience: every storage access is wrapped the way
 * lib/local-draft.ts does, and a draft is offered only for the very version it
 * was made on — if someone saved the document since, restoring would overwrite
 * their work, so such a draft is dropped. React-free; relative imports only.
 */

export interface StoredDraft<S> {
  userId: number;
  documentId: number;
  /** The document version the edits started from. */
  baseVersion: number;
  state: S;
  /** When it was written (ms since the epoch). */
  at: number;
}

export type Recovery<S> = { kind: "offer"; state: S; at: number } | { kind: "stale"; at: number } | null;

type Store = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export function draftStorageKey(userId: number, documentId: number): string {
  return `veye:designer-draft:${userId}:${documentId}`;
}

function browserStore(): Store | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null; // blocked storage (private browsing, policy)
  }
}

export function writeDraft<S>(draft: StoredDraft<S>, store: Store | null = browserStore()): void {
  try {
    store?.setItem(draftStorageKey(draft.userId, draft.documentId), JSON.stringify(draft));
  } catch {
    // Full or blocked storage: the draft is a convenience, never an error.
  }
}

export function clearDraft(userId: number, documentId: number, store: Store | null = browserStore()): void {
  try {
    store?.removeItem(draftStorageKey(userId, documentId));
  } catch {
    // as above
  }
}

export function readDraft<S>(userId: number, documentId: number, store: Store | null = browserStore()): StoredDraft<S> | null {
  try {
    const raw = store?.getItem(draftStorageKey(userId, documentId));
    if (!raw) return null;
    const draft = JSON.parse(raw) as StoredDraft<S>;
    if (draft.userId !== userId || draft.documentId !== documentId || typeof draft.baseVersion !== "number") return null;
    return draft;
  } catch {
    return null; // unreadable: treat as absent
  }
}

/**
 * What to offer when a document opens. `snapshot` is the adapter's, used to
 * tell whether the draft differs from what the server has. A pure read — it
 * runs during render; the designer removes a stale or matching draft itself
 * (it clears the stored work whenever the document is clean).
 */
export function findRecovery<S>(
  userId: number,
  documentId: number,
  serverVersion: number,
  serverSnapshot: string,
  snapshot: (state: S) => string,
  store: Store | null = browserStore(),
): Recovery<S> {
  const draft = readDraft<S>(userId, documentId, store);
  if (!draft) return null;
  if (draft.baseVersion !== serverVersion) return { kind: "stale", at: draft.at };
  let same = false;
  try {
    same = snapshot(draft.state) === serverSnapshot;
  } catch {
    same = true; // a draft from an older shape of the state: nothing safe to offer
  }
  if (same) return null;
  return { kind: "offer", state: draft.state, at: draft.at };
}
