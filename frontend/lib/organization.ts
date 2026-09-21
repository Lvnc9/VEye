/**
 * The organisation chart's data model and its pure logic (Phase 7).
 *
 * `GET /org/tree/` returns a *flat* list already in depth-first order; everything here builds on
 * that. Pure functions, no fetching — relative imports only (vitest has no `@/` alias).
 */

export type OrgNodeKind = "COMPANY" | "DOMAIN" | "UNIT" | "SECTION";

export interface OrgNode {
  id: number;
  parent: number | null;
  kind: OrgNodeKind;
  kind_label: string;
  name: string;
  depth: number;
  is_active: boolean;
  /** Viewer-relative flags: the very functions the write endpoints enforce (backend access.py). */
  can_edit: boolean;
  can_add_child: boolean;
  can_manage_members: boolean;
}

export interface OrgTreeNode extends OrgNode {
  children: OrgTreeNode[];
}

export interface OrgTreeResponse {
  truncated: boolean;
  nodes: OrgNode[];
}

export interface OrgMembership {
  id: number;
  user: number;
  user_name: string;
  user_title: string;
  user_is_active: boolean;
  node: number;
  node_name: string;
  node_kind: OrgNodeKind;
  is_primary: boolean;
  is_lead: boolean;
  position_label: string;
}

export interface Company {
  id: number;
  root: number;
  name: string;
  legal_name: string;
  national_id: string;
  logo_url: string | null;
  setup_step: string;
  setup_step_label: string;
  setup_completed_at: string | null;
}

export const ORG_KIND_LABELS: Record<OrgNodeKind, string> = {
  COMPANY: "شرکت",
  DOMAIN: "حوزه",
  UNIT: "واحد",
  SECTION: "بخش",
};

/** Tailwind classes per kind: a dot / badge colour, light-theme friendly. */
export const ORG_KIND_TONE: Record<OrgNodeKind, string> = {
  COMPANY: "bg-slate-800 text-white",
  DOMAIN: "bg-indigo-600 text-white",
  UNIT: "bg-sky-600 text-white",
  SECTION: "bg-emerald-600 text-white",
};

/**
 * Which kinds a node may hang under — the backend's parent-kind table (models.py
 * ALLOWED_PARENT_KINDS), read the other way round: what may I add *inside* a node of kind K?
 * A واحد may sit straight under the company (a company with no حوزه is valid).
 */
const CHILD_KINDS: Record<OrgNodeKind, OrgNodeKind[]> = {
  COMPANY: ["DOMAIN", "UNIT"],
  DOMAIN: ["UNIT"],
  UNIT: ["SECTION"],
  SECTION: [],
};

export function childKindsOf(kind: OrgNodeKind): OrgNodeKind[] {
  return CHILD_KINDS[kind];
}

/** The chart as a tree. Order-independent (a child listed before its parent still attaches), and
 *  siblings keep the order they arrived in. Returns the company root, or null for an empty chart. */
export function buildTree(nodes: OrgNode[]): OrgTreeNode | null {
  const byId = new Map<number, OrgTreeNode>();
  for (const node of nodes) byId.set(node.id, { ...node, children: [] });

  let root: OrgTreeNode | null = null;
  for (const node of nodes) {
    const treeNode = byId.get(node.id)!;
    const parent = node.parent === null ? undefined : byId.get(node.parent);
    if (parent) parent.children.push(treeNode);
    else if (node.kind === "COMPANY") root = treeNode;
  }
  return root;
}

/** Everything below `id`, depth-first, not including it. */
export function descendantsOf(nodes: OrgNode[], id: number): OrgNode[] {
  const childrenOf = new Map<number, OrgNode[]>();
  for (const node of nodes) {
    if (node.parent !== null) childrenOf.set(node.parent, [...(childrenOf.get(node.parent) ?? []), node]);
  }
  const result: OrgNode[] = [];
  const visit = (parentId: number) => {
    for (const child of childrenOf.get(parentId) ?? []) {
      result.push(child);
      visit(child.id);
    }
  };
  visit(id);
  return result;
}

/** The chain above `id`, company first, not including it. */
export function ancestorsOf(nodes: OrgNode[], id: number): OrgNode[] {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const chain: OrgNode[] = [];
  let current = byId.get(id);
  const seen = new Set<number>();
  while (current && current.parent !== null && !seen.has(current.id)) {
    seen.add(current.id);
    current = byId.get(current.parent);
    if (current) chain.unshift(current);
  }
  return chain;
}

export function countByKind(nodes: OrgNode[]): Record<OrgNodeKind, number> {
  const counts: Record<OrgNodeKind, number> = { COMPANY: 0, DOMAIN: 0, UNIT: 0, SECTION: 0 };
  for (const node of nodes) counts[node.kind] += 1;
  return counts;
}

export interface NodeOption {
  id: number;
  /** The name indented by depth, so a flat <select> still reads as a tree. */
  label: string;
  node: OrgNode;
}

/** Options for a <select> of nodes: depth-first order, indented, optionally limited by kind and
 *  hiding archived nodes (the default — nothing new may be placed in one). */
export function nodeOptions(
  nodes: OrgNode[],
  { kinds, includeArchived = false }: { kinds?: OrgNodeKind[]; includeArchived?: boolean } = {},
): NodeOption[] {
  return nodes
    .filter((node) => (includeArchived || node.is_active) && (!kinds || kinds.includes(node.kind)))
    .map((node) => ({
      id: node.id,
      label: `${"\xa0\xa0".repeat(node.depth)}${node.name}`,
      node,
    }));
}

const ZWNJ = new RegExp(String.fromCharCode(0x200c), "g");

/** The first letter(s) of a person's name for an avatar: up to two initials, ZWNJ-aware. */
export function initials(name: string): string {
  const words = name
    .replace(ZWNJ, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (words.length === 0) return "؟";
  if (words.length === 1) return Array.from(words[0])[0];
  return Array.from(words[0])[0] + Array.from(words[words.length - 1])[0];
}

/** «واحد فروش» within «حوزه شمال» — the breadcrumb of a node, company first. */
export function pathLabel(nodes: OrgNode[], id: number): string {
  const node = nodes.find((candidate) => candidate.id === id);
  if (!node) return "";
  return [...ancestorsOf(nodes, id), node].map((n) => n.name).join(" › ");
}
