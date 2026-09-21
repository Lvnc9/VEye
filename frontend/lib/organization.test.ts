import { describe, expect, it } from "vitest";
import {
  ancestorsOf,
  buildTree,
  childKindsOf,
  countByKind,
  descendantsOf,
  initials,
  nodeOptions,
  pathLabel,
  type OrgNode,
  type OrgNodeKind,
} from "./organization";

let nextId = 1;
const node = (over: Partial<OrgNode> & { name: string; kind: OrgNodeKind }): OrgNode => ({
  id: nextId++,
  parent: null,
  kind_label: "",
  depth: 0,
  is_active: true,
  can_edit: false,
  can_add_child: false,
  can_manage_members: false,
  ...over,
});

// company ─ D1 ─ U1 ─ S1
//              └ U2
//         └ U3 (a واحد straight under the company)
function sample() {
  nextId = 1;
  const company = node({ name: "شرکت", kind: "COMPANY" });
  const d1 = node({ name: "حوزه یک", kind: "DOMAIN", parent: company.id, depth: 1 });
  const u1 = node({ name: "واحد فروش", kind: "UNIT", parent: d1.id, depth: 2 });
  const s1 = node({ name: "بخش یک", kind: "SECTION", parent: u1.id, depth: 3 });
  const u2 = node({ name: "واحد مالی", kind: "UNIT", parent: d1.id, depth: 2 });
  const u3 = node({ name: "واحد مستقل", kind: "UNIT", parent: company.id, depth: 1 });
  return { nodes: [company, d1, u1, s1, u2, u3], company, d1, u1, s1, u2, u3 };
}

describe("buildTree", () => {
  it("nests a depth-first flat list, keeping sibling order", () => {
    const { nodes } = sample();
    const root = buildTree(nodes)!;
    expect(root.name).toBe("شرکت");
    expect(root.children.map((c) => c.name)).toEqual(["حوزه یک", "واحد مستقل"]);
    expect(root.children[0].children.map((c) => c.name)).toEqual(["واحد فروش", "واحد مالی"]);
    expect(root.children[0].children[0].children.map((c) => c.name)).toEqual(["بخش یک"]);
  });

  it("does not depend on the order the nodes arrive in", () => {
    const { nodes } = sample();
    const root = buildTree([...nodes].reverse())!;
    expect(root.name).toBe("شرکت");
    expect(root.children).toHaveLength(2);
    const domain = root.children.find((child) => child.kind === "DOMAIN")!; // siblings keep arrival order
    expect(domain.children).toHaveLength(2);
    expect(domain.children.find((child) => child.name === "واحد فروش")!.children).toHaveLength(1);
  });

  it("is null for an empty chart, and a company with no حوزه is a valid tree", () => {
    expect(buildTree([])).toBeNull();
    const { company, u3 } = sample();
    const root = buildTree([company, u3])!;
    expect(root.children.map((c) => c.kind)).toEqual(["UNIT"]);
  });

  it("does not mutate its input", () => {
    const { nodes } = sample();
    buildTree(nodes);
    expect("children" in nodes[0]).toBe(false);
  });
});

describe("descendantsOf / ancestorsOf", () => {
  it("collects everything below a node, depth-first, without the node", () => {
    const { nodes, d1, u3 } = sample();
    expect(descendantsOf(nodes, d1.id).map((n) => n.name)).toEqual(["واحد فروش", "بخش یک", "واحد مالی"]);
    expect(descendantsOf(nodes, u3.id)).toEqual([]);
  });

  it("collects the chain above a node, company first, without the node", () => {
    const { nodes, s1, company } = sample();
    expect(ancestorsOf(nodes, s1.id).map((n) => n.name)).toEqual(["شرکت", "حوزه یک", "واحد فروش"]);
    expect(ancestorsOf(nodes, company.id)).toEqual([]);
    expect(ancestorsOf(nodes, 999)).toEqual([]);
  });

  it("builds a breadcrumb", () => {
    const { nodes, s1, u3 } = sample();
    expect(pathLabel(nodes, s1.id)).toBe("شرکت › حوزه یک › واحد فروش › بخش یک");
    expect(pathLabel(nodes, u3.id)).toBe("شرکت › واحد مستقل");
    expect(pathLabel(nodes, 999)).toBe("");
  });
});

describe("kinds", () => {
  it("mirrors the backend's parent-kind table: what may go inside what", () => {
    expect(childKindsOf("COMPANY")).toEqual(["DOMAIN", "UNIT"]);
    expect(childKindsOf("DOMAIN")).toEqual(["UNIT"]);
    expect(childKindsOf("UNIT")).toEqual(["SECTION"]);
    expect(childKindsOf("SECTION")).toEqual([]);
  });

  it("counts nodes per kind", () => {
    const { nodes } = sample();
    expect(countByKind(nodes)).toEqual({ COMPANY: 1, DOMAIN: 1, UNIT: 3, SECTION: 1 });
  });
});

describe("nodeOptions", () => {
  it("indents by depth so a flat select still reads as a tree, and can filter by kind", () => {
    const { nodes } = sample();
    const options = nodeOptions(nodes, { kinds: ["UNIT", "SECTION"] });
    expect(options.map((o) => o.label.trim())).toEqual(["واحد فروش", "بخش یک", "واحد مالی", "واحد مستقل"]);
    expect(options[1].label.startsWith("\xa0".repeat(6))).toBe(true); // depth 3
  });

  it("hides archived nodes unless asked, since nothing new may go into one", () => {
    const { nodes, u2 } = sample();
    const archived = nodes.map((n) => (n.id === u2.id ? { ...n, is_active: false } : n));
    expect(nodeOptions(archived).map((o) => o.id)).not.toContain(u2.id);
    expect(nodeOptions(archived, { includeArchived: true }).map((o) => o.id)).toContain(u2.id);
  });
});

describe("initials", () => {
  it("takes the first and last word's first letter, treating ZWNJ as a space", () => {
    expect(initials("علی رضایی")).toBe("عر");
    expect(initials("علی اکبر رضایی")).toBe("عر");
    expect(initials("علی")).toBe("ع");
    expect(initials("  ")).toBe("؟");
    expect(initials("می" + String.fromCharCode(0x200c) + "نا")).toBe("من");
  });
});
