/**
 * The Responsibilities block's row logic (owner's redesign, 2026-09-30) — pure, so it is tested
 * without React. A row names a حوزه (only when the company has any) and a واحد, then says what the
 * واحد is responsible for; it prints «حوزه IT  واحد هوش مصنوعی  جهت <text>».
 *
 * The chart comes from `GET /org/tree/` (a flat list, depth-first). Relative imports only (vitest
 * has no `@/` alias).
 */
import type { OrgNode } from "./organization";
import type { ResponsibilityRow } from "./types";

export const MAX_RESPONSIBILITY_ROWS = 100;

export function emptyResponsibilityRow(): ResponsibilityRow {
  return { domain: null, unit: null, domain_name: "", unit_name: "", text: "" };
}

/** Does the company have any active حوزه? Then the first control of a row is «انتخاب حوزه»; otherwise it
 *  is «انتخاب واحد». */
export function companyHasDomains(nodes: OrgNode[]): boolean {
  return nodes.some((node) => node.kind === "DOMAIN" && node.is_active);
}

function companyId(nodes: OrgNode[]): number | null {
  return nodes.find((node) => node.kind === "COMPANY")?.id ?? null;
}

/** Active units that hang straight off the company, with no حوزه above them. */
export function standaloneUnits(nodes: OrgNode[]): OrgNode[] {
  const root = companyId(nodes);
  return nodes.filter((node) => node.kind === "UNIT" && node.is_active && node.parent === root);
}

/** The حوزه a row may pick: the active ones, plus the one it already names (even if archived since). */
export function domainOptions(nodes: OrgNode[], current: number | null): OrgNode[] {
  return nodes.filter((node) => node.kind === "DOMAIN" && (node.is_active || node.id === current));
}

/**
 * The واحد a row may pick, in chart order. With حوزه in the company only the chosen حوزه's units are
 * offered (or, after «بدون حوزه», the units under the company); without حوزه, every active unit.
 * The unit the row already names is kept even if archived since.
 */
export function unitOptions(nodes: OrgNode[], row: ResponsibilityRow, hasDomains: boolean): OrgNode[] {
  const root = companyId(nodes);
  return nodes.filter((node) => {
    if (node.kind !== "UNIT") return false;
    if (!node.is_active && node.id !== row.unit) return false;
    if (!hasDomains) return true;
    if (row.domain !== null) return node.parent === row.domain;
    return row.standalone === true && node.parent === root;
  });
}

/** Which control of a row comes next: the حوزه picker, the واحد picker, or (once a واحد is chosen, or
 *  the row already has text) the «توضیحات:» field. */
export type RowStage = "domain" | "unit" | "text";

export function rowStage(row: ResponsibilityRow, hasDomains: boolean): RowStage {
  if (row.unit !== null || row.unit_name !== "" || row.text !== "") return "text";
  if (!hasDomains) return "unit";
  return row.domain !== null || row.standalone === true ? "unit" : "domain";
}

/** The حوزه picked (null = «بدون حوزه»): forgets the واحد, which belonged to the old choice. */
export function pickDomain(row: ResponsibilityRow, domain: OrgNode | null): ResponsibilityRow {
  return {
    ...row,
    domain: domain?.id ?? null,
    domain_name: domain?.name ?? "",
    unit: null,
    unit_name: "",
    standalone: domain === null,
  };
}

/** The واحد picked. `domainOf` is its حوزه (null: it hangs straight off the company), so a company with
 *  حوزه never prints a واحد alone. */
export function pickUnit(row: ResponsibilityRow, unit: OrgNode, domainOf: OrgNode | null): ResponsibilityRow {
  return {
    ...row,
    unit: unit.id,
    unit_name: unit.name,
    domain: domainOf?.id ?? null,
    domain_name: domainOf?.name ?? "",
    standalone: domainOf === null,
  };
}

/** The حوزه a واحد belongs to, from the chart (null when it hangs off the company or is not in the list). */
export function domainOfUnit(nodes: OrgNode[], unit: OrgNode): OrgNode | null {
  const parent = nodes.find((node) => node.id === unit.parent);
  return parent?.kind === "DOMAIN" ? parent : null;
}

/** Back to the first control, keeping what was typed. */
export function clearChoice(row: ResponsibilityRow): ResponsibilityRow {
  return { ...row, domain: null, unit: null, domain_name: "", unit_name: "", standalone: false };
}

/** A row from the server: a saved واحد with no حوزه, in a company that has حوزه, is a standalone one. */
export function fromServerRow(row: ResponsibilityRow): ResponsibilityRow {
  return { ...row, standalone: row.domain === null && row.unit !== null };
}

/** What is sent: only the five fields the API knows. */
export function toPayloadRow(row: ResponsibilityRow) {
  const { domain, unit, domain_name, unit_name, text } = row;
  return { domain, unit, domain_name, unit_name, text };
}

/** Work restored from this browser's storage from before the redesign has the old shape (four fixed
 *  roles with a سمت and a ناظر, plus notes). Turn it into free-text rows like migration 0008 did. */
export interface LegacyRoleRow {
  role: string;
  post?: string;
  supervisor?: string;
  text?: string;
}

const LEGACY_LETTERS: Record<string, string> = { responder: "الف", receiver: "ب", cash_account: "ج", supervisor: "د" };

export function legacyRows(roles: LegacyRoleRow[] | undefined, notes: string[] | undefined): ResponsibilityRow[] {
  const rows: ResponsibilityRow[] = [];
  for (const role of roles ?? []) {
    const post = (role.post ?? "").trim();
    const supervisor = (role.supervisor ?? "").trim();
    const text = (role.text ?? "").trim();
    if (!post && !supervisor && !text) continue;
    const letter = LEGACY_LETTERS[role.role];
    const parts = [...(post ? [`سمت: ${post}`] : []), ...(supervisor ? [`ناظر: ${supervisor}`] : [])];
    const head = (letter ? `${letter}:  ` : "") + parts.join("    ");
    const joined = parts.length === 0 ? `${head}${text}` : text ? `${head}\n${text}` : head;
    rows.push({ ...emptyResponsibilityRow(), text: joined });
  }
  for (const note of notes ?? []) {
    if (note.trim()) rows.push({ ...emptyResponsibilityRow(), text: note.trim() });
  }
  return rows;
}
