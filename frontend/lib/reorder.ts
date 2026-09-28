/**
 * Reordering a list by drag-and-drop or by ↑/↓ — shared by the block designer
 * and the form designer. React-free.
 */

/** Moves the element at `from` so it ends up at index `to` (in the list without it). */
export function moveElement<T>(items: T[], from: number, to: number): T[] {
  if (from < 0 || from >= items.length) return items;
  const target = Math.max(0, Math.min(to, items.length - 1));
  if (target === from) return items;
  const next = items.slice();
  const [moved] = next.splice(from, 1);
  next.splice(target, 0, moved);
  return next;
}

/**
 * Where a dragged element lands when dropped on `over`, before or after it:
 * the index to pass to `moveElement`. Dropping an element on itself (either
 * half) leaves it where it is.
 */
export function dropIndex(from: number, over: number, after: boolean): number {
  const slot = after ? over + 1 : over; // insertion slot in the original list
  return slot > from ? slot - 1 : slot;
}

/** Inserts `element` after index `after` (-1 = at the start; past the end = at the end). */
export function insertAfter<T>(items: T[], element: T, after: number): T[] {
  const next = items.slice();
  next.splice(Math.min(after + 1, items.length), 0, element);
  return next;
}
