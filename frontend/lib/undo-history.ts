/**
 * Undo / redo for the designers (Phase 12). React-free: the designer keeps a
 * `History` next to its state and these functions move between them.
 *
 * Changes that follow each other within `COALESCE_MS` are one step, so a burst
 * of typing is undone at once rather than a letter at a time.
 */

export const COALESCE_MS = 600;
export const LIMIT = 100;

export interface History<S> {
  /** Earlier states, oldest first. */
  past: S[];
  /** States undone, the next redo first. */
  future: S[];
  /** When the last change was recorded (ms); 0 after an undo/redo, so the next change starts a new step. */
  lastAt: number;
}

export function emptyHistory<S>(): History<S> {
  return { past: [], future: [], lastAt: 0 };
}

/** A change from `previous` happened at `at`. A new change drops anything that could have been redone. */
export function record<S>(history: History<S>, previous: S, at: number): History<S> {
  if (history.past.length > 0 && history.lastAt > 0 && at - history.lastAt < COALESCE_MS) {
    return { past: history.past, future: [], lastAt: at };
  }
  const past = [...history.past, previous];
  return { past: past.length > LIMIT ? past.slice(past.length - LIMIT) : past, future: [], lastAt: at };
}

export function undo<S>(history: History<S>, current: S): { history: History<S>; state: S } | null {
  if (history.past.length === 0) return null;
  const state = history.past[history.past.length - 1];
  return {
    state,
    history: { past: history.past.slice(0, -1), future: [current, ...history.future], lastAt: 0 },
  };
}

export function redo<S>(history: History<S>, current: S): { history: History<S>; state: S } | null {
  if (history.future.length === 0) return null;
  const [state, ...future] = history.future;
  return { state, history: { past: [...history.past, current], future, lastAt: 0 } };
}
