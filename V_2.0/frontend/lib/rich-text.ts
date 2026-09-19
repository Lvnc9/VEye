/**
 * Inline text styling, in V_1.0's own format.
 *
 * Bold, italic and underline are stored as markers inside the text itself:
 * `**bold**`, `~~italic~~`, `--underline--`. V_1.0's editor inserted them
 * (other_folder/utils.py:784-788) and its PDF renderer parses exactly these
 * (to_make_pdf.py:458-541), so the text is stored verbatim with no conversion.
 *
 * The renderer matches each marker non-greedily and cannot nest one style
 * inside another, which is why `applyStyle` refuses to.
 */

export const MARKERS = { bold: "**", italic: "~~", underline: "--" } as const;
export type Style = keyof typeof MARKERS;

const ALL_MARKERS = Object.values(MARKERS);

export interface StyleResult {
  text: string;
  selStart: number;
  selEnd: number;
  /** Set when the change was refused; `text` is then the unchanged input. */
  error?: "inside-style";
}

function countOccurrences(haystack: string, needle: string): number {
  let count = 0;
  for (let i = haystack.indexOf(needle); i !== -1; i = haystack.indexOf(needle, i + needle.length)) {
    count += 1;
  }
  return count;
}

function stripMarkers(text: string): string {
  return ALL_MARKERS.reduce((acc, marker) => acc.split(marker).join(""), text);
}

/**
 * Toggle `style` on the selected range, V_1.0-style: one style at a time.
 *
 *  - Selection already wrapped by the marker (inside it, or including it): unwrap.
 *  - Selection inside some other styled region: refuse (nesting would print the
 *    marker characters literally in the PDF).
 *  - Otherwise: strip any markers the selection contains, then wrap it.
 *
 * The returned selection stays on the inner text, so pressing the same button
 * again toggles the style back off.
 */
export function applyStyle(text: string, selStart: number, selEnd: number, style: Style): StyleResult {
  if (selStart >= selEnd) return { text, selStart, selEnd };

  const marker = MARKERS[style];
  const before = text.slice(0, selStart);
  const selected = text.slice(selStart, selEnd);
  const after = text.slice(selEnd);

  // The selection sits just inside an existing pair of this marker.
  const opensBefore = before.endsWith(marker) && countOccurrences(before.slice(0, -marker.length), marker) % 2 === 0;
  if (opensBefore && after.startsWith(marker)) {
    return {
      text: before.slice(0, -marker.length) + selected + after.slice(marker.length),
      selStart: selStart - marker.length,
      selEnd: selEnd - marker.length,
    };
  }

  // The selection includes the whole pair, markers and all.
  if (selected.length >= 2 * marker.length && selected.startsWith(marker) && selected.endsWith(marker)) {
    const inner = selected.slice(marker.length, -marker.length);
    return { text: before + inner + after, selStart, selEnd: selStart + inner.length };
  }

  // Inside a region of any style: an odd number of its markers precede us.
  if (ALL_MARKERS.some((m) => countOccurrences(before, m) % 2 === 1)) {
    return { text, selStart, selEnd, error: "inside-style" };
  }

  const inner = stripMarkers(selected);
  const start = selStart + marker.length;
  return {
    text: before + marker + inner + marker + after,
    selStart: start,
    selEnd: start + inner.length,
  };
}

export interface Run {
  text: string;
  style?: Style;
}

/** Split text into plain and styled runs the way the PDF renderer does
 *  (`draw_rtl_styled_line`, to_make_pdf.py:458-541): one line at a time, each
 *  marker matched non-greedily, unmatched markers left as literal text. */
export function parseMarkers(text: string): Run[] {
  const runs: Run[] = [];
  const pattern = /\*\*.*?\*\*|~~.*?~~|--.*?--/g;
  let last = 0;

  for (const match of text.matchAll(pattern)) {
    const index = match.index ?? 0;
    if (index > last) runs.push({ text: text.slice(last, index) });
    const fragment = match[0];
    const style: Style = fragment.startsWith("**") ? "bold" : fragment.startsWith("~~") ? "italic" : "underline";
    const inner = fragment.slice(2, -2);
    if (inner) runs.push({ text: inner, style });
    last = index + fragment.length;
  }
  if (last < text.length) runs.push({ text: text.slice(last) });
  return runs;
}
