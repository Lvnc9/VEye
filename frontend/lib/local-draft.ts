"use client";

import { useState } from "react";

/**
 * A per-composer draft in `localStorage` (docs/12-phase-10-adr.md §D): the note composer, the
 * progress-update textarea and the meeting form all use one `useLocalDraft(key)` so half-typed text
 * survives an accidental navigation or a lost tab. Every storage access is wrapped in try/catch —
 * private browsing, a full quota, or a blocked store must never break the composer itself; a lost
 * draft is a nicety lost, not a bug (the same rule `lib/flash.ts` follows for sessionStorage).
 *
 * Relative imports only: vitest has no `@/` alias.
 */

/** `veye:draft:<userId>:<projectId>:<purpose>[:<objectiveId>]` — one key per composer instance. */
export function draftKey(userId: number, projectId: number, purpose: string, objectiveId?: number): string {
  const base = `veye:draft:${userId}:${projectId}:${purpose}`;
  return objectiveId === undefined ? base : `${base}:${objectiveId}`;
}

function readDraft(key: string): string {
  try {
    return window.localStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}

function writeDraft(key: string, value: string): void {
  try {
    if (value) window.localStorage.setItem(key, value);
    else window.localStorage.removeItem(key);
  } catch {
    // localStorage may be blocked (private browsing) or full; the draft is a convenience, not a
    // source of truth, so a failed write here must never surface as an error to the user.
  }
}

/**
 * `key` may be `null` while its parts (e.g. the signed-in user) are still loading — the hook then
 * behaves like a plain `useState("")`: nothing persists until a real key arrives. Returns
 * `[value, set, clear]`; callers clear the draft once their submit succeeds.
 */
export function useLocalDraft(key: string | null): [string, (value: string) => void, () => void] {
  const [state, setState] = useState<{ key: string | null; value: string }>(() => ({
    key,
    value: key ? readDraft(key) : "",
  }));

  // Reload from storage when `key` changes (e.g. the signed-in user resolves after this component's
  // first render) by adjusting state during rendering — React's documented alternative to an effect
  // that reads a prop and calls setState, which would cost an extra render/commit for no benefit here.
  if (state.key !== key) {
    setState({ key, value: key ? readDraft(key) : "" });
  }

  function set(next: string) {
    setState({ key, value: next });
    if (key) writeDraft(key, next);
  }

  function clear() {
    setState({ key, value: "" });
    if (key) writeDraft(key, "");
  }

  return [state.value, set, clear];
}
