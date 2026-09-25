/**
 * Placing people in the chart from the personnel screen (Phase 7.8, cascaded in Phase 10 §B).
 * Pure functions — relative imports only (vitest has no `@/` alias).
 *
 * Without this no بخش would ever have anyone in it: `/personnel/` creates accounts, and a person is
 * only *in* the organisation once they have a membership.
 *
 * The cascade is «حوزه» → «واحد» → «بخش», each step offering a terminal "place here" choice
 * alongside its children, so a placement can stop at any level (company root, a حوزه head, a واحد
 * head, or a بخش). Picking a value at one level always clears the levels below it — there is never
 * a stale, invisible choice further down the chain.
 */

import type { OrgNode, OrgNodeKind } from "./organization";
import type { User } from "./types";

// ---------------------------------------------------------------------------
// The three-level pick
// ---------------------------------------------------------------------------

export type DomainPick = { type: "company" } | { type: "no_domain" } | { type: "domain"; id: number };

export type UnitPick = { type: "domain_level" } | { type: "unit"; id: number };

export type SectionPick = { type: "unit_level" } | { type: "section"; id: number };

export interface PlacementForm {
  domain: DomainPick | null;
  unit: UnitPick | null;
  section: SectionPick | null;
  isLead: boolean;
  positionLabel: string;
}

export const EMPTY_PLACEMENT: PlacementForm = {
  domain: null,
  unit: null,
  section: null,
  isLead: false,
  positionLabel: "",
};

// ---------------------------------------------------------------------------
// Reading the chart
// ---------------------------------------------------------------------------

function companyOf(nodes: OrgNode[]): OrgNode | null {
  return nodes.find((node) => node.kind === "COMPANY" && node.is_active) ?? null;
}

function childrenOf(nodes: OrgNode[], kind: OrgNodeKind, parentId: number): OrgNode[] {
  return nodes.filter((node) => node.kind === kind && node.is_active && node.parent === parentId);
}

// ---------------------------------------------------------------------------
// Value <-> pick encoding, for a single <select> per level
// ---------------------------------------------------------------------------

function encodeDomainPick(pick: DomainPick | null): string {
  if (!pick) return "";
  if (pick.type === "domain") return `domain:${pick.id}`;
  return pick.type;
}

function decodeDomainPick(value: string): DomainPick | null {
  if (value === "") return null;
  if (value === "company" || value === "no_domain") return { type: value };
  const id = Number(value.slice("domain:".length));
  return { type: "domain", id };
}

function encodeUnitPick(pick: UnitPick | null): string {
  if (!pick) return "";
  if (pick.type === "unit") return `unit:${pick.id}`;
  return pick.type;
}

function decodeUnitPick(value: string): UnitPick | null {
  if (value === "") return null;
  if (value === "domain_level") return { type: "domain_level" };
  return { type: "unit", id: Number(value.slice("unit:".length)) };
}

function encodeSectionPick(pick: SectionPick | null): string {
  if (!pick) return "";
  if (pick.type === "section") return `section:${pick.id}`;
  return pick.type;
}

function decodeSectionPick(value: string): SectionPick | null {
  if (value === "") return null;
  if (value === "unit_level") return { type: "unit_level" };
  return { type: "section", id: Number(value.slice("section:".length)) };
}

/** Change the حوزه step's answer, clearing واحد and بخش below it. */
export function pickDomain(form: PlacementForm, value: string): PlacementForm {
  return { ...form, domain: decodeDomainPick(value), unit: null, section: null };
}

/** Change the واحد step's answer, clearing بخش below it. */
export function pickUnit(form: PlacementForm, value: string): PlacementForm {
  return { ...form, unit: decodeUnitPick(value), section: null };
}

/** Change the بخش step's answer (the leaf — nothing below it to clear). */
export function pickSection(form: PlacementForm, value: string): PlacementForm {
  return { ...form, section: decodeSectionPick(value) };
}

// ---------------------------------------------------------------------------
// What to show
// ---------------------------------------------------------------------------

export interface PlacementOption {
  value: string;
  label: string;
}

export interface PlacementStep {
  level: "domain" | "unit" | "section";
  value: string;
  options: PlacementOption[];
}

/**
 * The steps to render, in order, given how far the form has gone: always حوزه; واحد once حوزه
 * resolved to something other than «خود شرکت»; بخش once a واحد (not «در سطح همین حوزه») is chosen.
 */
export function placementOptions(nodes: OrgNode[], form: PlacementForm): PlacementStep[] {
  const steps: PlacementStep[] = [];
  const company = companyOf(nodes);

  const domainOptions: PlacementOption[] = [
    ...(company ? [{ value: "company", label: "خود شرکت" }] : []),
    { value: "no_domain", label: "بدون حوزه (مستقیم زیر شرکت)" },
    ...childrenOf(nodes, "DOMAIN", company?.id ?? -1).map((node) => ({ value: `domain:${node.id}`, label: node.name })),
  ];
  steps.push({ level: "domain", value: encodeDomainPick(form.domain), options: domainOptions });

  if (!form.domain || form.domain.type === "company") return steps;

  const unitParentId = form.domain.type === "domain" ? form.domain.id : (company?.id ?? -1);
  const unitOptions: PlacementOption[] = [
    ...(form.domain.type === "domain" ? [{ value: "domain_level", label: "در سطح همین حوزه" }] : []),
    ...childrenOf(nodes, "UNIT", unitParentId).map((node) => ({ value: `unit:${node.id}`, label: node.name })),
  ];
  steps.push({ level: "unit", value: encodeUnitPick(form.unit), options: unitOptions });

  if (!form.unit || form.unit.type === "domain_level") return steps;

  const sectionOptions: PlacementOption[] = [
    { value: "unit_level", label: "در سطح همین واحد" },
    ...childrenOf(nodes, "SECTION", form.unit.id).map((node) => ({ value: `section:${node.id}`, label: node.name })),
  ];
  steps.push({ level: "section", value: encodeSectionPick(form.section), options: sectionOptions });

  return steps;
}

// ---------------------------------------------------------------------------
// The answer: which node, if any
// ---------------------------------------------------------------------------

/** The node the cascade currently resolves to, or `null` while it is still mid-pick (or empty). */
export function resolvePlacement(nodes: OrgNode[], form: PlacementForm): { node: number } | null {
  const company = companyOf(nodes);
  if (!form.domain) return null;
  if (form.domain.type === "company") return company ? { node: company.id } : null;

  if (!form.unit) return null;
  if (form.unit.type === "domain_level") {
    return form.domain.type === "domain" ? { node: form.domain.id } : null;
  }

  if (!form.section) return null;
  if (form.section.type === "unit_level") return { node: form.unit.id };
  return { node: form.section.id };
}

export function hasPlacement(nodes: OrgNode[], form: PlacementForm): boolean {
  return resolvePlacement(nodes, form) !== null;
}

export interface PlacementPayload {
  node: number;
  is_lead: boolean;
  position_label: string;
}

/** The `placement` object `POST /personnel/` accepts, or `undefined` while nothing is resolved. */
export function placementPayload(nodes: OrgNode[], form: PlacementForm): PlacementPayload | undefined {
  const resolved = resolvePlacement(nodes, form);
  if (!resolved) return undefined;
  return { node: resolved.node, is_lead: form.isLead, position_label: form.positionLabel.trim() };
}

/** The `POST /org/memberships/` body for placing an already-registered person (`UnassignedPeople`). */
export function membershipBody(userId: number, nodes: OrgNode[], form: PlacementForm) {
  const payload = placementPayload(nodes, form);
  if (!payload) return null;
  return { user: userId, ...payload };
}

/** «پروفایل پرسنل با موفقیت ثبت شد» plus, when placed, where. */
export function placedMessage(nodeName: string | null): string {
  return nodeName
    ? `پروفایل پرسنل با موفقیت ثبت شد و در «${nodeName}» قرار گرفت.`
    : "پروفایل پرسنل با موفقیت ثبت شد.";
}

/** What `POST /personnel/` returns: the person, and — only when `placement` was sent — their new membership. */
export interface RegisteredPerson extends User {
  membership?: {
    id: number;
    node: number;
    node_name: string;
    node_kind: OrgNodeKind;
    is_lead: boolean;
    is_primary: boolean;
    position_label: string;
  };
}

/** `?unassigned=1`: people with no place in the chart yet, for the «بدون جایگاه» list. */
export const UNASSIGNED_PATH = "/org/people/?unassigned=1&page_size=50";
