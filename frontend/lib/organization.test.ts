import { describe, expect, it } from "vitest";
import {
  ZOOM_MAX,
  ZOOM_MIN,
  ancestorsOf,
  buildTree,
  chartLayout,
  childKindsOf,
  clampZoom,
  countByKind,
  descendantsOf,
  fitView,
  initials,
  memberCaption,
  nodeOptions,
  pathLabel,
  zoomAround,
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

describe("chartLayout (the building)", () => {
  it("makes the company the building, each حوزه a floor, each واحد a room, each بخش a desk", () => {
    const { nodes } = sample();
    const layout = chartLayout(nodes)!;
    expect(layout.company.name).toBe("شرکت");
    expect(layout.floors.map((f) => f.node?.name ?? null)).toEqual(["حوزه یک", null]); // ground floor last
    const [floor, ground] = layout.floors;
    expect(floor.rooms.map((r) => r.node.name)).toEqual(["واحد فروش", "واحد مالی"]);
    expect(floor.rooms[0].desks.map((d) => d.name)).toEqual(["بخش یک"]);
    expect(floor.rooms[1].desks).toEqual([]);
    expect(ground.rooms.map((r) => r.node.name)).toEqual(["واحد مستقل"]);
  });

  it("gives a company with no حوزه a single implicit ground floor", () => {
    const { company, u3 } = sample();
    const layout = chartLayout([company, u3])!;
    expect(layout.floors).toHaveLength(1);
    expect(layout.floors[0].node).toBeNull();
    expect(layout.floors[0].rooms).toHaveLength(1);
  });

  it("is a lone building for a company with nothing in it, and null for an empty chart", () => {
    const { company } = sample();
    expect(chartLayout([company])!.floors).toEqual([]);
    expect(chartLayout([])).toBeNull();
  });

  it("leaves archived nodes out unless asked, without hiding the company itself", () => {
    const { nodes, u2, d1 } = sample();
    const archived = nodes.map((n) => (n.id === u2.id ? { ...n, is_active: false } : n));
    expect(chartLayout(archived)!.floors[0].rooms.map((r) => r.node.name)).toEqual(["واحد فروش"]);
    expect(chartLayout(archived, true)!.floors[0].rooms.map((r) => r.node.name)).toEqual(["واحد فروش", "واحد مالی"]);
    const floorGone = nodes.map((n) => (n.id === d1.id ? { ...n, is_active: false } : n));
    expect(chartLayout(floorGone)!.floors.map((f) => f.node?.name ?? null)).toEqual([null]); // its rooms go with it
  });
});

describe("zoom", () => {
  it("clamps to the supported range and survives nonsense", () => {
    expect(clampZoom(10)).toBe(ZOOM_MAX);
    expect(clampZoom(0.01)).toBe(ZOOM_MIN);
    expect(clampZoom(1.2)).toBe(1.2);
    expect(clampZoom(Number.NaN)).toBe(1);
  });

  it("keeps the point under the cursor fixed while zooming", () => {
    const view = { x: 40, y: 10, zoom: 1 };
    const origin = { x: 200, y: 100 };
    const next = zoomAround(view, 2, origin);
    expect(next.zoom).toBe(2);
    // the content point under the origin before and after must be the same
    const before = { x: (origin.x - view.x) / view.zoom, y: (origin.y - view.y) / view.zoom };
    const after = { x: (origin.x - next.x) / next.zoom, y: (origin.y - next.y) / next.zoom };
    expect(after.x).toBeCloseTo(before.x);
    expect(after.y).toBeCloseTo(before.y);
  });

  it("does not drift once the limit is reached", () => {
    const atMax = { x: 5, y: 5, zoom: ZOOM_MAX };
    expect(zoomAround(atMax, 2, { x: 50, y: 50 })).toEqual(atMax);
  });
});

describe("memberCaption", () => {
  it("prefers the written position, else says who leads what, else nothing", () => {
    expect(memberCaption({ is_lead: true, position_label: "رئیس فروش" }, "واحد فروش")).toBe("رئیس فروش");
    expect(memberCaption({ is_lead: true, position_label: "" }, "واحد فروش")).toBe("مسئول واحد فروش");
    expect(memberCaption({ is_lead: false, position_label: "" }, "واحد فروش")).toBe("");
  });
});

describe("fitView", () => {
  it("shows a building that fits at 100%, centred", () => {
    expect(fitView({ width: 1000, height: 600 }, { width: 400, height: 300 })).toEqual({ x: 300, y: 24, zoom: 1 });
  });

  it("zooms out just enough for a wide building, and keeps it centred", () => {
    const view = fitView({ width: 1000, height: 600 }, { width: 2000, height: 900 });
    expect(view.zoom).toBeCloseTo(0.476, 2); // (1000 - 48) / 2000
    expect(view.x).toBeCloseTo(24, 5); // fills the width minus padding
  });

  it("also fits a tall building, so the bottom floor is not cut off", () => {
    const view = fitView({ width: 1000, height: 600 }, { width: 400, height: 1200 });
    expect(view.zoom).toBeCloseTo(0.46, 2); // (600 - 48) / 1200
    expect(view.x).toBeCloseTo((1000 - 400 * view.zoom) / 2, 5);
  });

  it("never zooms below the minimum, and survives an unmeasured viewport", () => {
    expect(fitView({ width: 300, height: 300 }, { width: 100000, height: 10 }).zoom).toBe(ZOOM_MIN);
    expect(fitView({ width: 0, height: 0 }, { width: 400, height: 300 })).toEqual({ x: 0, y: 0, zoom: 1 });
    expect(fitView({ width: 500, height: 500 }, { width: 0, height: 0 })).toEqual({ x: 0, y: 0, zoom: 1 });
  });
});
