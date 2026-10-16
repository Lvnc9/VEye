/**
 * The ⌘K palette (Phase 22): the shape `GET /search/?q=` answers with, and the pure logic of moving
 * through its results. Relative imports only (vitest has no `@/` alias).
 */

export interface SearchItem {
  id: number;
  title: string;
  subtitle: string;
  url: string;
}

export interface SearchGroup {
  type: string;
  label: string;
  items: SearchItem[];
}

export interface SearchResponse {
  query: string;
  groups: SearchGroup[];
}

/** The server needs two letters; this is checked on the trimmed text. */
export const SEARCH_MIN_LENGTH = 2;
export const SEARCH_DEBOUNCE_MS = 250;

export function searchable(text: string): boolean {
  return text.trim().length >= SEARCH_MIN_LENGTH;
}

/** One flat list, in the order shown, each remembering its group — what the arrow keys walk. */
export interface FlatResult extends SearchItem {
  group: string;
  /** Stable DOM id, for `aria-activedescendant`. */
  key: string;
}

export function flattenResults(groups: SearchGroup[]): FlatResult[] {
  return groups.flatMap((group) =>
    group.items.map((item) => ({ ...item, group: group.label, key: `search-${group.type}-${item.id}` })),
  );
}

/** Move the highlight by `step` (±1), wrapping at both ends; -1 means nothing is highlighted yet. */
export function moveActive(current: number, step: 1 | -1, length: number): number {
  if (length <= 0) return -1;
  if (current < 0) return step === 1 ? 0 : length - 1;
  return (current + step + length) % length;
}

/** ⌘K on a Mac, Ctrl+K elsewhere (either works on both, so a Mac keyboard attached to Windows is fine). */
export function isPaletteShortcut(event: { key: string; metaKey: boolean; ctrlKey: boolean; altKey: boolean }): boolean {
  return event.key.toLowerCase() === "k" && (event.metaKey || event.ctrlKey) && !event.altKey;
}

/** The event the top bar's button fires and the palette listens for. */
export const OPEN_SEARCH_EVENT = "veye:open-search";
