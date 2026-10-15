/**
 * Comparing two revisions of a document (Phase 21, «مقایسه با بازنگری قبلی»). Pure: two `/content/`
 * payloads in, rows for a side-by-side view out. No dependency: a small LCS does both levels.
 *
 * 1. Each section becomes a *block* — its label and its text, one string per line (a block's id differs
 *    between revisions, since a revision is a copy, so ids cannot be matched).
 * 2. Blocks are aligned: an LCS over exact (type + text) matches finds what did not change; between two such
 *    anchors, blocks of the same type are paired in order as «changed», the rest are «added» / «removed».
 * 3. A changed pair is diffed word by word, so the screen can highlight exactly what moved.
 * Relative imports only (vitest has no `@/` alias).
 */
import { ELEMENT_KINDS } from "./form-designer";
import { SECTION_TYPE_LABELS, type ContentResponse, type SectionType, type ServerSection } from "./types";

export interface Block {
  type: string;
  label: string;
  lines: string[];
}

export interface Token {
  op: "same" | "add" | "del";
  text: string;
}

export type DiffRow =
  | { kind: "same"; label: string; old: Block; new: Block }
  | { kind: "changed"; label: string; old: Block; new: Block; oldTokens: Token[]; newTokens: Token[] }
  | { kind: "added"; label: string; new: Block }
  | { kind: "removed"; label: string; old: Block };

const FORM_ELEMENT = "Form Element";
const FORM_SKIP_KEYS = new Set(["id", "type", "kind", "key", "style", "align", "level", "height", "width", "widths"]);

/** Every string inside a form element, depth first — a fair summary of what it says. */
function strings(value: unknown, out: string[] = []): string[] {
  if (typeof value === "string") {
    if (value.trim()) out.push(value.trim());
  } else if (Array.isArray(value)) {
    for (const item of value) strings(item, out);
  } else if (value && typeof value === "object") {
    for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
      if (!FORM_SKIP_KEYS.has(key)) strings(item, out);
    }
  }
  return out;
}

function nonEmpty(lines: (string | undefined | null)[]): string[] {
  return lines.map((line) => (line ?? "").trim()).filter(Boolean);
}

export function toBlock(section: ServerSection | Record<string, unknown>): Block {
  const type = String((section as { type: string }).type);
  if (type === FORM_ELEMENT) {
    const kind = String((section as { kind?: string }).kind ?? "");
    const label = ELEMENT_KINDS.find((entry) => entry.kind === kind)?.label ?? kind;
    return { type: `${FORM_ELEMENT}:${kind}`, label, lines: strings(section) };
  }
  const s = section as ServerSection;
  const label = SECTION_TYPE_LABELS[type as SectionType] ?? type;
  switch (s.type) {
    case "Short Explanation":
      return { type, label, lines: nonEmpty(s.lines) };
    case "Long Explanation":
      return { type, label, lines: nonEmpty([s.heading, ...s.body.split("\n"), ...s.extra_boxes]) };
    case "Responsibilities":
      return {
        type,
        label,
        lines: s.rows.map((row) => [[row.domain_name, row.unit_name].filter(Boolean).join(" › "), row.text].filter(Boolean).join(": ")),
      };
    case "Changes Table":
      return { type, label, lines: nonEmpty(s.rows.map((row) => row.text)) };
    case "Attachment":
      return {
        type,
        label,
        lines: s.items.map((item) => [item.document?.full_code, item.caption].filter(Boolean).join(" — ")),
      };
    default:
      return { type, label, lines: [] };
  }
}

/** The blocks of a payload, footnotes last (they print on every page and change with a revision too). */
export function blocksOf(content: Pick<ContentResponse, "sections" | "footnote1" | "footnote2">): Block[] {
  const blocks = content.sections.map((section) => toBlock(section));
  const footnotes = nonEmpty([content.footnote1, content.footnote2]);
  if (footnotes.length) blocks.push({ type: "footnotes", label: "پاورقی", lines: footnotes });
  return blocks;
}

/** Longest common subsequence of two lists under `equal`: the index pairs that match, in order. */
export function lcsPairs<A, B>(a: A[], b: B[], equal: (x: A, y: B) => boolean): [number, number][] {
  const n = a.length;
  const m = b.length;
  const table: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      table[i][j] = equal(a[i], b[j]) ? table[i + 1][j + 1] + 1 : Math.max(table[i + 1][j], table[i][j + 1]);
    }
  }
  const pairs: [number, number][] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (equal(a[i], b[j])) {
      pairs.push([i, j]);
      i++;
      j++;
    } else if (table[i + 1][j] >= table[i][j + 1]) {
      i++;
    } else {
      j++;
    }
  }
  return pairs;
}

const sameBlock = (x: Block, y: Block) => x.type === y.type && x.lines.join("\n") === y.lines.join("\n");

/** Word-level diff of two texts: tokens of the old side (same / del) and of the new side (same / add). */
export function diffWords(oldText: string, newText: string): { oldTokens: Token[]; newTokens: Token[] } {
  const a = oldText.split(/(\s+)/).filter((part) => part !== "");
  const b = newText.split(/(\s+)/).filter((part) => part !== "");
  const pairs = lcsPairs(a, b, (x, y) => x === y);
  const oldTokens: Token[] = [];
  const newTokens: Token[] = [];
  let i = 0;
  let j = 0;
  const push = (list: Token[], op: Token["op"], text: string) => {
    const last = list[list.length - 1];
    if (last && last.op === op) last.text += text;
    else list.push({ op, text });
  };
  for (const [pi, pj] of [...pairs, [a.length, b.length] as [number, number]]) {
    while (i < pi) push(oldTokens, "del", a[i++]);
    while (j < pj) push(newTokens, "add", b[j++]);
    if (pi < a.length && pj < b.length) {
      push(oldTokens, "same", a[pi]);
      push(newTokens, "same", b[pj]);
      i = pi + 1;
      j = pj + 1;
    }
  }
  return { oldTokens, newTokens };
}

/** Align two revisions' blocks into side-by-side rows, in the new revision's order. */
export function diffBlocks(oldBlocks: Block[], newBlocks: Block[]): DiffRow[] {
  const anchors = lcsPairs(oldBlocks, newBlocks, sameBlock);
  const rows: DiffRow[] = [];
  let i = 0;
  let j = 0;
  for (const [ai, aj] of [...anchors, [oldBlocks.length, newBlocks.length] as [number, number]]) {
    // Between anchors: pair blocks of the same type in order; whatever is left was added or removed.
    const olds = oldBlocks.slice(i, ai);
    const news = newBlocks.slice(j, aj);
    const used = new Set<number>();
    for (const block of news) {
      const match = olds.findIndex((candidate, index) => !used.has(index) && candidate.type === block.type);
      if (match >= 0) {
        used.add(match);
        const old = olds[match];
        const words = diffWords(old.lines.join("\n"), block.lines.join("\n"));
        rows.push({ kind: "changed", label: block.label, old, new: block, ...words });
      } else {
        rows.push({ kind: "added", label: block.label, new: block });
      }
    }
    olds.forEach((old, index) => {
      if (!used.has(index)) rows.push({ kind: "removed", label: old.label, old });
    });
    if (ai < oldBlocks.length && aj < newBlocks.length) {
      rows.push({ kind: "same", label: newBlocks[aj].label, old: oldBlocks[ai], new: newBlocks[aj] });
    }
    i = ai + 1;
    j = aj + 1;
  }
  return rows;
}

export function diffContents(
  oldContent: Pick<ContentResponse, "sections" | "footnote1" | "footnote2">,
  newContent: Pick<ContentResponse, "sections" | "footnote1" | "footnote2">,
): DiffRow[] {
  return diffBlocks(blocksOf(oldContent), blocksOf(newContent));
}

export function changeCount(rows: DiffRow[]): number {
  return rows.filter((row) => row.kind !== "same").length;
}
