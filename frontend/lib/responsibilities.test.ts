import { describe, expect, it } from "vitest";
import type { OrgNode, OrgNodeKind } from "./organization";
import {
  clearChoice,
  companyHasDomains,
  domainOfUnit,
  domainOptions,
  emptyResponsibilityRow,
  fromServerRow,
  legacyRows,
  pickDomain,
  pickUnit,
  rowStage,
  standaloneUnits,
  toPayloadRow,
  unitOptions,
} from "./responsibilities";

let next = 1;
const node = (kind: OrgNodeKind, name: string, parent: number | null, active = true): OrgNode => ({
  id: next++, parent, kind, kind_label: "", name, depth: 0, is_active: active,
  can_edit: false, can_add_child: false, can_manage_members: false,
});

// شرکت ─ IT ─ هوش مصنوعی, توسعه (archived)
//      ├ فروش ─ بستن معاملات
//      └ مدیریت سیستم‌ها (a واحد straight under the company)
function chart() {
  next = 1;
  const root = node("COMPANY", "شرکت", null);
  const it = node("DOMAIN", "IT", root.id);
  const ai = node("UNIT", "هوش مصنوعی", it.id);
  const dev = node("UNIT", "توسعه", it.id, false);
  const sales = node("DOMAIN", "فروش", root.id);
  const deals = node("UNIT", "بستن معاملات", sales.id);
  const free = node("UNIT", "مدیریت سیستم‌ها", root.id);
  return { root, it, ai, dev, sales, deals, free, nodes: [root, it, ai, dev, sales, deals, free] };
}

describe("which controls a row shows", () => {
  it("knows whether the company has any active حوزه", () => {
    const c = chart();
    expect(companyHasDomains(c.nodes)).toBe(true);
    expect(companyHasDomains([c.root, c.free])).toBe(false);
    expect(companyHasDomains([c.root, node("DOMAIN", "بایگانی", c.root.id, false)])).toBe(false);
  });

  it("starts at the حوزه picker when there are حوزه, and at the واحد picker when there are none", () => {
    expect(rowStage(emptyResponsibilityRow(), true)).toBe("domain");
    expect(rowStage(emptyResponsibilityRow(), false)).toBe("unit");
  });

  it("moves on to the واحد after a حوزه (or «بدون حوزه»), and to the text after a واحد", () => {
    const c = chart();
    const withDomain = pickDomain(emptyResponsibilityRow(), c.it);
    expect(rowStage(withDomain, true)).toBe("unit");
    expect(rowStage(pickDomain(emptyResponsibilityRow(), null), true)).toBe("unit");
    expect(rowStage(pickUnit(withDomain, c.ai, c.it), true)).toBe("text");
  });

  it("shows the text field for a row that only has text (a converted old row)", () => {
    expect(rowStage({ ...emptyResponsibilityRow(), text: "الف: قدیمی" }, true)).toBe("text");
  });
});

describe("what a row may pick", () => {
  it("offers the active حوزه, plus the one the row already names", () => {
    const c = chart();
    expect(domainOptions(c.nodes, null).map((n) => n.name)).toEqual(["IT", "فروش"]);
    const archived = node("DOMAIN", "قدیمی", c.root.id, false);
    expect(domainOptions([...c.nodes, archived], archived.id).map((n) => n.name)).toContain("قدیمی");
    expect(domainOptions([...c.nodes, archived], null).map((n) => n.name)).not.toContain("قدیمی");
  });

  it("offers only the chosen حوزه's active units", () => {
    const c = chart();
    const row = pickDomain(emptyResponsibilityRow(), c.it);
    expect(unitOptions(c.nodes, row, true).map((n) => n.name)).toEqual(["هوش مصنوعی"]);
    expect(unitOptions(c.nodes, pickDomain(emptyResponsibilityRow(), c.sales), true).map((n) => n.name)).toEqual(["بستن معاملات"]);
  });

  it("keeps an archived واحد the row already names", () => {
    const c = chart();
    const row = { ...pickDomain(emptyResponsibilityRow(), c.it), unit: c.dev.id, unit_name: "توسعه" };
    expect(unitOptions(c.nodes, row, true).map((n) => n.name)).toEqual(["هوش مصنوعی", "توسعه"]);
  });

  it("offers the units under the company after «بدون حوزه», and nothing before a حوزه is chosen", () => {
    const c = chart();
    expect(unitOptions(c.nodes, pickDomain(emptyResponsibilityRow(), null), true).map((n) => n.name)).toEqual(["مدیریت سیستم‌ها"]);
    expect(unitOptions(c.nodes, emptyResponsibilityRow(), true)).toEqual([]);
    expect(standaloneUnits(c.nodes).map((n) => n.name)).toEqual(["مدیریت سیستم‌ها"]);
  });

  it("offers every active unit when the company has no حوزه", () => {
    const root = node("COMPANY", "شرکت", null);
    const a = node("UNIT", "الف", root.id);
    const b = node("UNIT", "ب", root.id);
    expect(unitOptions([root, a, b], emptyResponsibilityRow(), false).map((n) => n.name)).toEqual(["الف", "ب"]);
  });
});

describe("picking", () => {
  it("picking a حوزه forgets the واحد that belonged to the old choice", () => {
    const c = chart();
    const row = pickUnit(pickDomain(emptyResponsibilityRow(), c.it), c.ai, c.it);
    const changed = pickDomain(row, c.sales);
    expect([changed.unit, changed.unit_name, changed.domain_name]).toEqual([null, "", "فروش"]);
  });

  it("a واحد brings its حوزه along; one under the company has none", () => {
    const c = chart();
    expect(domainOfUnit(c.nodes, c.ai)?.name).toBe("IT");
    expect(domainOfUnit(c.nodes, c.free)).toBeNull();
    const row = pickUnit(emptyResponsibilityRow(), c.ai, domainOfUnit(c.nodes, c.ai));
    expect([row.domain, row.domain_name, row.unit, row.unit_name]).toEqual([c.it.id, "IT", c.ai.id, "هوش مصنوعی"]);
    expect(pickUnit(emptyResponsibilityRow(), c.free, null).standalone).toBe(true);
  });

  it("clearing the choice keeps what was typed", () => {
    const c = chart();
    const row = { ...pickUnit(emptyResponsibilityRow(), c.ai, c.it), text: "کار" };
    expect(clearChoice(row)).toMatchObject({ domain: null, unit: null, domain_name: "", unit_name: "", text: "کار" });
  });

  it("a saved واحد with no حوزه comes back as standalone", () => {
    expect(fromServerRow({ ...emptyResponsibilityRow(), unit: 5, unit_name: "مستقل" }).standalone).toBe(true);
    expect(fromServerRow({ ...emptyResponsibilityRow(), domain: 2, unit: 5 }).standalone).toBe(false);
  });

  it("sends five fields", () => {
    expect(Object.keys(toPayloadRow({ ...emptyResponsibilityRow(), standalone: true })).sort()).toEqual(
      ["domain", "domain_name", "text", "unit", "unit_name"],
    );
  });
});

describe("rows from before the redesign", () => {
  it("writes each old row as one free line, like migration 0008", () => {
    const rows = legacyRows(
      [
        { role: "responder", post: "مدیر", supervisor: "ناظر", text: "شرح" },
        { role: "receiver", post: "", supervisor: "", text: "فقط شرح" },
        { role: "cash_account", post: "حسابدار" },
        { role: "supervisor" },
      ],
      ["یادداشت"],
    );
    expect(rows.map((r) => r.text)).toEqual([
      "الف:  سمت: مدیر    ناظر: ناظر\nشرح",
      "ب:  فقط شرح",
      "ج:  سمت: حسابدار",
      "یادداشت",
    ]);
  });
});
