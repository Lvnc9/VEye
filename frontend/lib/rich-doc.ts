/**
 * The rich body of a تشریحی بلند block (owner's request, 2026-09-29): a ProseMirror / Tiptap
 * document the server validates against a whitelist (`backend/apps/documents/rich_content.py`)
 * and the PDF renderer prints (`backend/apps/pdfgen/richtext.py`).
 *
 * Pure functions, no React and no Tiptap — relative imports only (vitest has no `@/` alias).
 * The constants below mirror the server's; change them together.
 */
import { parseMarkers } from "./rich-text";

export interface RichNode {
  type: string;
  attrs?: Record<string, unknown>;
  content?: RichNode[];
  marks?: { type: string; attrs?: Record<string, unknown> }[];
  text?: string;
}

/** What a block stores and the server returns: a versioned envelope around the document. */
export interface RichDoc {
  v: 1;
  doc: { type: "doc"; content: RichNode[] };
}

/** Text colours the editor offers (label for the tooltip; the server accepts exactly these). */
export const PALETTE: readonly { value: string; label: string }[] = [
  { value: "#000000", label: "مشکی" },
  { value: "#4b5563", label: "خاکستری" },
  { value: "#dc2626", label: "قرمز" },
  { value: "#ea580c", label: "نارنجی" },
  { value: "#16a34a", label: "سبز" },
  { value: "#1d4ed8", label: "آبی" },
  { value: "#7e22ce", label: "بنفش" },
];

export const FONT_SIZES = [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32] as const;
export const DEFAULT_FONT_SIZE = 12;
export const MAX_INDENT = 6;
export const MAX_LIST_DEPTH = 3;
export const MAX_TABLE_COLUMNS = 20;
export const MAX_TABLE_ROWS = 200;
export const LINK_PATTERN = /^(https?:\/\/|mailto:)[^\s\x00-\x1f\x7f<>"']{1,2000}$/i;

export function emptyRich(): RichDoc {
  return { v: 1, doc: { type: "doc", content: [{ type: "paragraph" }] } };
}

/** The nearest size the editor offers (a pasted 13.5 pt or 18 px becomes a size the printer knows). */
export function snapFontSize(points: number): number {
  return FONT_SIZES.reduce((best, size) => (Math.abs(size - points) < Math.abs(best - points) ? size : best));
}

/** A CSS colour (`#DC2626`, `rgb(220, 38, 38)`) as a palette hex, or null when it is not one of ours. */
export function paletteColor(css: string | null | undefined): string | null {
  if (!css) return null;
  const value = css.trim().toLowerCase();
  let hex = value;
  const rgb = /^rgba?\(\s*(\d{1,3})\s*[, ]\s*(\d{1,3})\s*[, ]\s*(\d{1,3})/.exec(value);
  if (rgb) {
    hex = "#" + [rgb[1], rgb[2], rgb[3]].map((n) => Math.min(255, Number(n)).toString(16).padStart(2, "0")).join("");
  }
  return PALETTE.some((color) => color.value === hex) ? hex : null;
}

/** A CSS `font-size` (`14pt`, `18.6667px`) as the nearest offered size in points, or null. */
export function fontSizeFromCss(css: string | null | undefined): number | null {
  if (!css) return null;
  const match = /^\s*([\d.]+)\s*(pt|px)\s*$/i.exec(css);
  if (!match) return null;
  const points = match[2].toLowerCase() === "px" ? Number(match[1]) * 0.75 : Number(match[1]);
  return Number.isFinite(points) && points > 0 ? snapFontSize(points) : null;
}

/** Whether a link may be stored: http, https or mailto, as the server requires. */
export function isAllowedLink(href: string): boolean {
  return LINK_PATTERN.test(href);
}

// --------------------------------------------------------------------------
// Old marker text → a document
// --------------------------------------------------------------------------

function inline(line: string): RichNode[] {
  const parts: RichNode[] = [];
  for (const piece of parseMarkers(line)) {
    if (!piece.text) continue;
    const node: RichNode = { type: "text", text: piece.text };
    if (piece.style === "bold") node.marks = [{ type: "bold" }];
    else if (piece.style === "italic") node.marks = [{ type: "italic" }];
    else if (piece.style === "underline") node.marks = [{ type: "underline" }];
    parts.push(node);
  }
  return parts;
}

/**
 * The document a legacy block opens as in the editor: every line of the old body a paragraph
 * (markers become marks, blank lines blank paragraphs) and each extra box after it, a blank line
 * between — the same order and gaps the PDF printed. Nothing is stored until the user edits.
 */
export function legacyToRich(body: string, extraBoxes: string[]): RichDoc {
  const chunks = [body, ...extraBoxes.filter((box) => box.trim() !== "")];
  const lines: string[] = [];
  chunks.forEach((chunk, index) => {
    if (index > 0 && lines.length > 0) lines.push("");
    if (chunk === "" && index === 0) return;
    lines.push(...chunk.replace(/\r\n?/g, "\n").split("\n"));
  });
  const content = lines.map((line): RichNode => {
    const runs = inline(line);
    return runs.length ? { type: "paragraph", content: runs } : { type: "paragraph" };
  });
  return { v: 1, doc: { type: "doc", content: content.length ? content : [{ type: "paragraph" }] } };
}

/** The document as plain lines — for the placeholder «empty» check and tests. */
export function richText(rich: RichDoc | null): string {
  if (!rich) return "";
  const walk = (node: RichNode): string =>
    node.type === "text" ? (node.text ?? "") : node.type === "hardBreak" ? "\n" : (node.content ?? []).map(walk).join("");
  return rich.doc.content.map(walk).join("\n").trim();
}
