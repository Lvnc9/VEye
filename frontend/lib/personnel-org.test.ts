import { describe, expect, it } from "vitest";
import type { OrgNode } from "./organization";
import {
  EMPTY_PLACEMENT,
  hasPlacement,
  membershipBody,
  pickDomain,
  pickSection,
  pickUnit,
  placedMessage,
  placementOptions,
  placementPayload,
  resolvePlacement,
  UNASSIGNED_PATH,
  type PlacementForm,
} from "./personnel-org";

/** company ─ D1 ─ U1 ─ S1
 *               └ U2 (no بخش)
 *          └ U3 (loose, straight under the company) */
function node(partial: Partial<OrgNode> & Pick<OrgNode, "id" | "kind" | "parent" | "name">): OrgNode {
  return {
    depth: 0,
    is_active: true,
    kind_label: "",
    can_edit: true,
    can_add_child: true,
    can_manage_members: true,
    ...partial,
  };
}

const COMPANY = node({ id: 1, kind: "COMPANY", parent: null, name: "شرکت نمونه" });
const D1 = node({ id: 2, kind: "DOMAIN", parent: 1, name: "حوزه یک" });
const U1 = node({ id: 3, kind: "UNIT", parent: 2, name: "واحد فروش" });
const S1 = node({ id: 4, kind: "SECTION", parent: 3, name: "بخش یک" });
const U2 = node({ id: 5, kind: "UNIT", parent: 2, name: "واحد مالی" });
const U3 = node({ id: 6, kind: "UNIT", parent: 1, name: "واحد مستقل" });
const NODES: OrgNode[] = [COMPANY, D1, U1, S1, U2, U3];

describe("placementOptions", () => {
  it("always starts with the حوزه step: خود شرکت, بدون حوزه, then every حوزه", () => {
    const [domainStep] = placementOptions(NODES, EMPTY_PLACEMENT);
    expect(domainStep.level).toBe("domain");
    expect(domainStep.options.map((o) => o.value)).toEqual(["company", "no_domain", "domain:2"]);
  });

  it("offers no more steps until حوزه resolves to something other than خود شرکت", () => {
    const form = pickDomain(EMPTY_PLACEMENT, "company");
    expect(placementOptions(NODES, form)).toHaveLength(1);
  });

  it("after a specific حوزه, offers its واحد plus «در سطح همین حوزه»", () => {
    const form = pickDomain(EMPTY_PLACEMENT, "domain:2");
    const steps = placementOptions(NODES, form);
    expect(steps).toHaveLength(2);
    expect(steps[1].options.map((o) => o.value)).toEqual(["domain_level", "unit:3", "unit:5"]);
  });

  it("after «بدون حوزه», offers only the واحد straight under the company — no «در سطح همین حوزه»", () => {
    const form = pickDomain(EMPTY_PLACEMENT, "no_domain");
    const steps = placementOptions(NODES, form);
    expect(steps).toHaveLength(2);
    expect(steps[1].options.map((o) => o.value)).toEqual(["unit:6"]);
  });

  it("after a واحد with بخش, offers them plus «در سطح همین واحد»", () => {
    const form = pickUnit(pickDomain(EMPTY_PLACEMENT, "domain:2"), "unit:3");
    const steps = placementOptions(NODES, form);
    expect(steps).toHaveLength(3);
    expect(steps[2].options.map((o) => o.value)).toEqual(["unit_level", "section:4"]);
  });

  it("after a واحد with no بخش, still offers the بخش step, just without any بخش", () => {
    const form = pickUnit(pickDomain(EMPTY_PLACEMENT, "domain:2"), "unit:5");
    const steps = placementOptions(NODES, form);
    expect(steps).toHaveLength(3);
    expect(steps[2].options.map((o) => o.value)).toEqual(["unit_level"]);
  });

  it("stops at واحد when «در سطح همین حوزه» was chosen — no بخش step", () => {
    const form = pickUnit(pickDomain(EMPTY_PLACEMENT, "domain:2"), "domain_level");
    expect(placementOptions(NODES, form)).toHaveLength(2);
  });
});

describe("changing a level clears everything below it", () => {
  it("picking a different حوزه drops the واحد and بخش already chosen", () => {
    let form = pickDomain(EMPTY_PLACEMENT, "domain:2");
    form = pickUnit(form, "unit:3");
    form = pickSection(form, "section:4");
    expect(resolvePlacement(NODES, form)).toEqual({ node: 4 });

    form = pickDomain(form, "no_domain");
    expect(form.unit).toBeNull();
    expect(form.section).toBeNull();
    expect(resolvePlacement(NODES, form)).toBeNull();
  });

  it("picking a different واحد drops the بخش already chosen", () => {
    let form = pickUnit(pickDomain(EMPTY_PLACEMENT, "domain:2"), "unit:3");
    form = pickSection(form, "section:4");
    form = pickUnit(form, "unit:5");
    expect(form.section).toBeNull();
  });
});

describe("resolvePlacement", () => {
  it("is null before anything is picked", () => {
    expect(resolvePlacement(NODES, EMPTY_PLACEMENT)).toBeNull();
  });

  it("خود شرکت resolves to the company root", () => {
    expect(resolvePlacement(NODES, pickDomain(EMPTY_PLACEMENT, "company"))).toEqual({ node: 1 });
  });

  it("در سطح همین حوزه resolves to that حوزه", () => {
    const form = pickUnit(pickDomain(EMPTY_PLACEMENT, "domain:2"), "domain_level");
    expect(resolvePlacement(NODES, form)).toEqual({ node: 2 });
  });

  it("در سطح همین واحد resolves to that واحد", () => {
    const form = pickSection(pickUnit(pickDomain(EMPTY_PLACEMENT, "domain:2"), "unit:3"), "unit_level");
    expect(resolvePlacement(NODES, form)).toEqual({ node: 3 });
  });

  it("a chosen بخش resolves to itself", () => {
    const form = pickSection(pickUnit(pickDomain(EMPTY_PLACEMENT, "domain:2"), "unit:3"), "section:4");
    expect(resolvePlacement(NODES, form)).toEqual({ node: 4 });
  });

  it("بدون حوزه then a loose واحد resolves to that واحد's بخش step, not the واحد itself, until بخش answers", () => {
    const form = pickUnit(pickDomain(EMPTY_PLACEMENT, "no_domain"), "unit:6");
    expect(resolvePlacement(NODES, form)).toBeNull();
    expect(resolvePlacement(NODES, pickSection(form, "unit_level"))).toEqual({ node: 6 });
  });
});

describe("hasPlacement / placementPayload", () => {
  it("is false, and undefined, before the cascade resolves", () => {
    expect(hasPlacement(NODES, EMPTY_PLACEMENT)).toBe(false);
    expect(placementPayload(NODES, EMPTY_PLACEMENT)).toBeUndefined();
  });

  it("builds {node, is_lead, position_label}, trimming the label", () => {
    const form: PlacementForm = { ...pickDomain(EMPTY_PLACEMENT, "company"), isLead: true, positionLabel: "  رئیس  " };
    expect(placementPayload(NODES, form)).toEqual({ node: 1, is_lead: true, position_label: "رئیس" });
  });

  it("does not make someone مسئول unless asked", () => {
    const form = pickDomain(EMPTY_PLACEMENT, "company");
    expect(placementPayload(NODES, form)).toEqual({ node: 1, is_lead: false, position_label: "" });
  });
});

describe("membershipBody", () => {
  it("is null while nothing is resolved", () => {
    expect(membershipBody(42, NODES, EMPTY_PLACEMENT)).toBeNull();
  });

  it("adds the user id to the placement payload", () => {
    const form = pickDomain(EMPTY_PLACEMENT, "company");
    expect(membershipBody(42, NODES, form)).toEqual({ user: 42, node: 1, is_lead: false, position_label: "" });
  });
});

describe("placedMessage", () => {
  it("says where, by node name", () => {
    expect(placedMessage("بخش فروش")).toBe("پروفایل پرسنل با موفقیت ثبت شد و در «بخش فروش» قرار گرفت.");
  });

  it("is a plain success when nobody was placed", () => {
    expect(placedMessage(null)).toBe("پروفایل پرسنل با موفقیت ثبت شد.");
  });
});

describe("the unassigned list", () => {
  it("asks the people directory for those with no membership", () => {
    expect(UNASSIGNED_PATH).toContain("unassigned=1");
  });
});
