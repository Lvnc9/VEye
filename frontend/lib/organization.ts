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

// ---------------------------------------------------------------------------
// The building: how the chart is laid out
// ---------------------------------------------------------------------------

/** A واحد as a room, with its بخش as desks. */
export interface Room {
  node: OrgTreeNode;
  desks: OrgTreeNode[];
}

/** A حوزه as a floor. `node` is null for the implicit ground floor, which holds the واحد that hang
 *  straight under the company (a company with no حوزه is just one ground floor). */
export interface Floor {
  node: OrgTreeNode | null;
  rooms: Room[];
}

export interface ChartLayout {
  company: OrgTreeNode;
  floors: Floor[];
}

/**
 * The building metaphor as data: company = the building, حوزه = floors, واحد = rooms, بخش = desks.
 * Archived nodes are left out unless asked for. Floors keep the tree's order; the ground floor
 * (loose واحد) comes last.
 */
export function chartLayout(nodes: OrgNode[], showArchived = false): ChartLayout | null {
  const company = buildTree(nodes.filter((node) => showArchived || node.is_active || node.kind === "COMPANY"));
  if (!company) return null;

  const room = (unit: OrgTreeNode): Room => ({
    node: unit,
    desks: unit.children.filter((child) => child.kind === "SECTION"),
  });

  const floors: Floor[] = company.children
    .filter((child) => child.kind === "DOMAIN")
    .map((domain) => ({
      node: domain,
      rooms: domain.children.filter((child) => child.kind === "UNIT").map(room),
    }));

  const loose = company.children.filter((child) => child.kind === "UNIT").map(room);
  if (loose.length > 0) floors.push({ node: null, rooms: loose });
  return { company, floors };
}

export const ZOOM_MIN = 0.4;
export const ZOOM_MAX = 2.5;

export function clampZoom(zoom: number): number {
  if (!Number.isFinite(zoom)) return 1;
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, zoom));
}

/** Zoom by a factor around a point of the viewport (so the thing under the cursor stays put). */
export function zoomAround(
  view: { x: number; y: number; zoom: number },
  factor: number,
  origin: { x: number; y: number },
): { x: number; y: number; zoom: number } {
  const zoom = clampZoom(view.zoom * factor);
  const ratio = zoom / view.zoom;
  return { zoom, x: origin.x - (origin.x - view.x) * ratio, y: origin.y - (origin.y - view.y) * ratio };
}

/**
 * The view that shows the whole building: zoomed out just enough to fit the viewport (never zoomed
 * *in* past 100%), centred horizontally, near the top. Assumes a transform origin of (0, 0).
 */
export function fitView(
  viewport: { width: number; height: number },
  content: { width: number; height: number },
  padding = 24,
): { x: number; y: number; zoom: number } {
  if (content.width <= 0 || content.height <= 0 || viewport.width <= 0) return { x: 0, y: 0, zoom: 1 };
  const zoom = clampZoom(
    Math.min(1, (viewport.width - padding * 2) / content.width, (viewport.height - padding * 2) / content.height),
  );
  return { zoom, x: (viewport.width - content.width * zoom) / 2, y: padding };
}

export interface Person {
  id: number;
  full_name: string;
  title: string;
  is_active: boolean;
  memberships: {
    id: number;
    node: number;
    node_name: string;
    node_kind: OrgNodeKind;
    is_primary: boolean;
    is_lead: boolean;
    position_label: string;
  }[];
}

/** «مسئول واحد فروش» when they lead, else their own position label, else nothing. */
export function memberCaption(membership: Pick<OrgMembership, "is_lead" | "position_label">, nodeName: string): string {
  if (membership.position_label) return membership.position_label;
  return membership.is_lead ? `مسئول ${nodeName}` : "";
}
