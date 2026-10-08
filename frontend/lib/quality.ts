/**
 * The quality module's data model and pure logic (Phase 18): non-conformances, their corrective
 * actions, internal audits, the risk register and the history. No fetching here — what can be tested without a network, so the screens
 * stay thin. Relative imports only (vitest has no `@/` alias).
 */

import { formatJalali, toPersianDigits } from "./jalali";

export type NcSource = "AUDIT" | "COMPLAINT" | "INSPECTION" | "INTERNAL" | "OTHER";
export type NcSeverity = "MINOR" | "MAJOR" | "CRITICAL";
export type NcStatus = "OPEN" | "IN_PROGRESS" | "CLOSED" | "REJECTED";
export type ActionStatus = "TODO" | "IN_PROGRESS" | "DONE" | "VERIFIED" | "CANCELLED";
export type AuditStatus = "PLANNED" | "IN_PROGRESS" | "COMPLETED" | "CANCELLED";

// Mirrors of the backend's labels (quality/models.py) — the server sends `*_label` with every row; these
// serve the filter dropdowns and forms, where there is no row yet.
export const NC_SOURCE_LABELS: Record<NcSource, string> = {
  AUDIT: "ممیزی",
  COMPLAINT: "شکایت",
  INSPECTION: "بازرسی",
  INTERNAL: "گزارش داخلی",
  OTHER: "سایر",
};

export const NC_SEVERITY_LABELS: Record<NcSeverity, string> = {
  MINOR: "جزئی",
  MAJOR: "عمده",
  CRITICAL: "بحرانی",
};

export const NC_STATUS_LABELS: Record<NcStatus, string> = {
  OPEN: "ثبت‌شده، منتظر بررسی",
  IN_PROGRESS: "در دست اقدام",
  CLOSED: "بسته‌شده",
  REJECTED: "ردشده",
};

export const ACTION_STATUS_LABELS: Record<ActionStatus, string> = {
  TODO: "انجام نشده",
  IN_PROGRESS: "در حال انجام",
  DONE: "انجام شد، منتظر تایید",
  VERIFIED: "تایید شد",
  CANCELLED: "لغو شد",
};

export const AUDIT_STATUS_LABELS: Record<AuditStatus, string> = {
  PLANNED: "برنامه‌ریزی‌شده",
  IN_PROGRESS: "در حال انجام",
  COMPLETED: "انجام‌شده",
  CANCELLED: "لغو شد",
};

/** The tone vocabulary of `components/ui/Badge`. */
export type QualityTone = "neutral" | "brand" | "success" | "warning" | "danger" | "info" | "violet";

export const NC_STATUS_TONE: Record<NcStatus, QualityTone> = {
  OPEN: "warning",
  IN_PROGRESS: "brand",
  CLOSED: "success",
  REJECTED: "neutral",
};

export const NC_SEVERITY_TONE: Record<NcSeverity, QualityTone> = {
  MINOR: "neutral",
  MAJOR: "warning",
  CRITICAL: "danger",
};

export const AUDIT_STATUS_TONE: Record<AuditStatus, QualityTone> = {
  PLANNED: "info",
  IN_PROGRESS: "brand",
  COMPLETED: "success",
  CANCELLED: "neutral",
};

export interface NonConformance {
  id: number;
  /** `NC-0042` — the id, zero-padded, built by the server. */
  code: string;
  title: string;
  description: string;
  source: NcSource;
  source_label: string;
  severity: NcSeverity;
  severity_label: string;
  status: NcStatus;
  status_label: string;
  owner_node: number;
  owner_node_name: string;
  reported_by: number;
  reported_by_name: string;
  detected_on: string;
  related_document: number | null;
  related_document_code: string | null;
  related_document_title: string | null;
  /** The audit that raised it (a finding), if any. The code and title are shown to whoever reads the
   *  record; `can_view_audit` says whether *this viewer* may open the audit's page. */
  audit: number | null;
  audit_code: string | null;
  audit_title: string | null;
  can_view_audit: boolean;
  root_cause: string;
  rejection_reason: string;
  effectiveness_note: string;
  accepted_at: string | null;
  closed_at: string | null;
  created_at: string;
  /** Derived by the server from the actions, never stored. Cancelled actions are not counted. */
  actions_total: number;
  actions_verified: number;
  actions_overdue: number;
  /** What the viewer may do *right now* — the same functions the endpoints enforce. */
  can_edit: boolean;
  can_triage: boolean;
  can_reopen: boolean;
  can_add_action: boolean;
  can_close: boolean;
}

export interface QualityEvent {
  id: number;
  kind: string;
  kind_label: string;
  nc: number | null;
  nc_code: string | null;
  nc_title: string | null;
  audit: number | null;
  audit_code: string | null;
  audit_title: string | null;
  risk: number | null;
  risk_code: string | null;
  risk_title: string | null;
  actor_name: string;
  actor_title: string;
  subject_title: string;
  from_status: string;
  to_status: string;
  from_status_label: string;
  to_status_label: string;
  note: string;
  created_at: string;
}

// ---------------------------------------------------------------------------
// The list
// ---------------------------------------------------------------------------

export type NcMine = "" | "reported" | "assigned" | "manage";

export interface NcFilters {
  q: string;
  status: NcStatus | "";
  severity: NcSeverity | "";
  source: NcSource | "";
  mine: NcMine;
  overdue: boolean;
}

export const EMPTY_NC_FILTERS: NcFilters = { q: "", status: "", severity: "", source: "", mine: "", overdue: false };

export function hasActiveFilters(filters: NcFilters): boolean {
  return Boolean(filters.q.trim() || filters.status || filters.severity || filters.source || filters.mine || filters.overdue);
}

/** The query string of `GET /quality/nonconformances/` — an empty filter sends nothing at all (the
 *  server treats an unknown value as "matches nothing", so a stray `status=` must never be sent). */
export function ncQueryParams(filters: NcFilters, page: number, pageSize: number): Record<string, string | number> {
  const params: Record<string, string | number> = { page, page_size: pageSize };
  if (filters.q.trim()) params.q = filters.q.trim();
  if (filters.status) params.status = filters.status;
  if (filters.severity) params.severity = filters.severity;
  if (filters.source) params.source = filters.source;
  if (filters.mine) params.mine = filters.mine;
  if (filters.overdue) params.overdue = "1";
  return params;
}

/** «۲ از ۳ اقدام تایید شده» — or «بدون اقدام» while there is no plan (a record cannot close without one). */
export function actionsSummary(nc: Pick<NonConformance, "actions_total" | "actions_verified">): string {
  if (nc.actions_total === 0) return "بدون اقدام";
  return `${toPersianDigits(nc.actions_verified)} از ${toPersianDigits(nc.actions_total)} اقدام تایید شده`;
}

/** 0–100, or `null` with nothing to measure (an empty bar, not a misleading 0 %). */
export function actionsProgress(nc: Pick<NonConformance, "actions_total" | "actions_verified">): number | null {
  if (nc.actions_total === 0) return null;
  return Math.round((100 * nc.actions_verified) / nc.actions_total);
}

// ---------------------------------------------------------------------------
// The report / edit form
// ---------------------------------------------------------------------------

export const TITLE_MAX = 255;
export const TEXT_MAX = 4000;

export interface NcForm {
  title: string;
  description: string;
  owner_node: number | null;
  source: NcSource;
  severity: NcSeverity;
  /** ISO date. */
  detected_on: string;
  related_document: number | null;
}

/** The node a report starts on: the reporter's own home (primary membership), else any membership. */
export function defaultOwnerNode(memberships: { node: number; is_primary: boolean }[] | undefined): number | null {
  if (!memberships || memberships.length === 0) return null;
  return (memberships.find((m) => m.is_primary) ?? memberships[0]).node;
}

export function emptyForm(ownerNode: number | null, today: string): NcForm {
  return {
    title: "",
    description: "",
    owner_node: ownerNode,
    source: "INTERNAL",
    severity: "MINOR",
    detected_on: today,
    related_document: null,
  };
}

export function formFromNc(nc: NonConformance): NcForm {
  return {
    title: nc.title,
    description: nc.description,
    owner_node: nc.owner_node,
    source: nc.source,
    severity: nc.severity,
    detected_on: nc.detected_on,
    related_document: nc.related_document,
  };
}

/** An early Persian message per field, so a form never needs a round trip to say "required". The server
 *  re-checks everything (including a node that has been archived since the page loaded). */
export function validateNcForm(form: NcForm, today: string): Partial<Record<keyof NcForm, string>> {
  const errors: Partial<Record<keyof NcForm, string>> = {};
  if (!form.title.trim()) errors.title = "عنوان را بنویسید.";
  else if (form.title.trim().length > TITLE_MAX) errors.title = `عنوان نباید بیش از ${toPersianDigits(TITLE_MAX)} نویسه باشد.`;
  if (!form.description.trim()) errors.description = "شرح مشکل را بنویسید.";
  else if (form.description.trim().length > TEXT_MAX) errors.description = `شرح نباید بیش از ${toPersianDigits(TEXT_MAX)} نویسه باشد.`;
  if (form.owner_node === null) errors.owner_node = "گرهٔ مربوط را انتخاب کنید.";
  if (!form.detected_on) errors.detected_on = "تاریخ کشف را مشخص کنید.";
  else if (form.detected_on > today) errors.detected_on = "تاریخ کشف نمی‌تواند در آینده باشد.";
  return errors;
}

/** The `POST` body. A blank document is left out rather than sent as null noise. */
export function createPayload(form: NcForm): Record<string, unknown> {
  const body: Record<string, unknown> = {
    title: form.title.trim(),
    description: form.description.trim(),
    owner_node: form.owner_node,
    source: form.source,
    severity: form.severity,
    detected_on: form.detected_on,
  };
  if (form.related_document !== null) body.related_document = form.related_document;
  return body;
}

/** The `PATCH` body: only what differs from the record, so an edit that changes nothing sends nothing
 *  (and the server, which logs only real changes, has nothing to log). */
export function patchPayload(nc: NonConformance, form: NcForm): Record<string, unknown> {
  const original = formFromNc(nc);
  const body: Record<string, unknown> = {};
  const next = { ...form, title: form.title.trim(), description: form.description.trim() };
  for (const key of Object.keys(next) as (keyof NcForm)[]) {
    if (next[key] !== original[key]) body[key] = next[key];
  }
  return body;
}

// ---------------------------------------------------------------------------
// The history
// ---------------------------------------------------------------------------

export const QUALITY_EVENT_TONE: Record<string, string> = {
  nc_reported: "bg-brand-500",
  nc_edited: "bg-amber-500",
  nc_accepted: "bg-teal-500",
  nc_rejected: "bg-rose-500",
  nc_closed: "bg-emerald-500",
  nc_reopened: "bg-orange-500",
  action_added: "bg-brand-500",
  action_edited: "bg-amber-500",
  action_assigned: "bg-teal-500",
  action_status_changed: "bg-amber-500",
  action_due_changed: "bg-orange-500",
  action_verified: "bg-emerald-500",
  action_verification_failed: "bg-rose-500",
  action_cancelled: "bg-slate-400",
  audit_planned: "bg-brand-500",
  audit_edited: "bg-amber-500",
  audit_auditor_changed: "bg-teal-500",
  audit_started: "bg-brand-500",
  audit_completed: "bg-emerald-500",
  audit_cancelled: "bg-slate-400",
  finding_raised: "bg-orange-500",
  risk_created: "bg-brand-500",
  risk_edited: "bg-amber-500",
  risk_assessed: "bg-violet-500",
  risk_status_changed: "bg-teal-500",
};

/** The second line of a history entry — what the kind alone does not say: a before → after, a deadline
 *  moving, or the reason someone typed. Empty when the kind label says it all. */
export function qualityEventDetail(event: QualityEvent): string {
  if (event.kind === "action_due_changed") {
    return `${formatJalali(event.from_status)} ← ${formatJalali(event.to_status)}`;
  }
  if (event.kind === "action_assigned" || event.kind === "audit_auditor_changed") return event.note;
  if (event.kind === "audit_planned") return `ممیز اصلی: ${event.note}`;
  if (event.kind === "risk_created") return `ارزیابی: ${event.note}`;
  if (event.from_status_label && event.to_status_label && event.kind !== "nc_rejected") {
    const move = `${event.from_status_label} ← ${event.to_status_label}`;
    return event.note ? `${move} — ${event.note}` : move;
  }
  return event.note;
}

// ---------------------------------------------------------------------------
// Corrective actions (slice 4)
// ---------------------------------------------------------------------------

export const ACTION_STATUS_TONE: Record<ActionStatus, QualityTone> = {
  TODO: "neutral",
  IN_PROGRESS: "brand",
  DONE: "warning",
  VERIFIED: "success",
  CANCELLED: "neutral",
};

export interface CorrectiveAction {
  id: number;
  nc: number;
  title: string;
  description: string;
  assignee: number;
  assignee_name: string;
  assignee_title: string;
  /** A person deactivated after being assigned: the action stays, and a manager reassigns it. */
  assignee_is_active: boolean;
  due_on: string;
  status: ActionStatus;
  status_label: string;
  /** Still the assignee's to do *and* past its deadline — a DONE action waits on a verifier, it is not late. */
  is_overdue: boolean;
  completed_at: string | null;
  verified_by_name: string | null;
  verified_at: string | null;
  verification_note: string;
  cancel_reason: string;
  created_at: string;
  /** What the viewer may do right now — the same functions the endpoints enforce. */
  can_edit: boolean;
  can_set_status: boolean;
  can_verify: boolean;
  can_cancel: boolean;
}

/** One status button: where it goes and what it says. */
export interface StatusButton {
  status: ActionStatus;
  label: string;
  /** A step *forward* is the primary button; stepping back is quiet. */
  forward: boolean;
}

/** The status moves the viewer may make by hand — the server's graph (`quality/services.STATUS_GRAPH`)
 *  with a label per move, offered only when the server says `can_set_status`. VERIFIED and CANCELLED are
 *  never offered here: they have their own dialogs. */
export function statusButtons(action: Pick<CorrectiveAction, "status" | "can_set_status">): StatusButton[] {
  if (!action.can_set_status) return [];
  switch (action.status) {
    case "TODO":
      return [{ status: "IN_PROGRESS", label: "شروع کار", forward: true }];
    case "IN_PROGRESS":
      return [
        { status: "DONE", label: "انجام شد", forward: true },
        { status: "TODO", label: "بازگشت به انجام‌نشده", forward: false },
      ];
    case "DONE":
      return [{ status: "IN_PROGRESS", label: "بازگشت به در حال انجام", forward: false }];
    default:
      return [];
  }
}

/** Why the close button is missing, for a manager looking at a record being worked — or `null` when it is
 *  available (or the viewer could not close it anyway). The rule is the server's: at least one action and
 *  every non-cancelled one verified; the effectiveness note is typed in the dialog. */
export function closeHint(
  nc: Pick<NonConformance, "status" | "can_add_action" | "can_close" | "actions_total" | "actions_verified">,
): string | null {
  if (nc.status !== "IN_PROGRESS" || !nc.can_add_action || nc.can_close) return null;
  if (nc.actions_total === 0) return "برای بستن، دست‌کم یک اقدام اصلاحی لازم است.";
  const unverified = nc.actions_total - nc.actions_verified;
  return `برای بستن، ${toPersianDigits(unverified)} اقدام دیگر باید تایید شود.`;
}

export interface ActionForm {
  title: string;
  description: string;
  assignee: number | null;
  /** ISO date. */
  due_on: string;
}

export function emptyActionForm(): ActionForm {
  return { title: "", description: "", assignee: null, due_on: "" };
}

export function actionFormFrom(action: CorrectiveAction): ActionForm {
  return { title: action.title, description: action.description, assignee: action.assignee, due_on: action.due_on };
}

/** Early Persian messages, as for the report form. A deadline in the past is refused only when it is *new*
 *  or *changed* — an overdue action must stay editable (its title, say) without being re-dated, which is
 *  exactly the server's rule. */
export function validateActionForm(
  form: ActionForm,
  today: string,
  original?: Pick<CorrectiveAction, "due_on">,
): Partial<Record<keyof ActionForm, string>> {
  const errors: Partial<Record<keyof ActionForm, string>> = {};
  if (!form.title.trim()) errors.title = "عنوان اقدام را بنویسید.";
  else if (form.title.trim().length > TITLE_MAX) errors.title = `عنوان نباید بیش از ${toPersianDigits(TITLE_MAX)} نویسه باشد.`;
  if (form.description.trim().length > TEXT_MAX) errors.description = `شرح نباید بیش از ${toPersianDigits(TEXT_MAX)} نویسه باشد.`;
  if (form.assignee === null) errors.assignee = "مسئول انجام اقدام را انتخاب کنید.";
  if (!form.due_on) errors.due_on = "مهلت را مشخص کنید.";
  else if (form.due_on < today && form.due_on !== original?.due_on) errors.due_on = "مهلت نمی‌تواند در گذشته باشد.";
  return errors;
}

export function actionCreatePayload(form: ActionForm): Record<string, unknown> {
  return {
    title: form.title.trim(),
    description: form.description.trim(),
    assignee: form.assignee,
    due_on: form.due_on,
  };
}

/** Only what changed, so an edit that changes nothing sends nothing (and logs nothing). */
export function actionPatchPayload(action: CorrectiveAction, form: ActionForm): Record<string, unknown> {
  const original = actionFormFrom(action);
  const next = { ...form, title: form.title.trim(), description: form.description.trim() };
  const body: Record<string, unknown> = {};
  for (const key of Object.keys(next) as (keyof ActionForm)[]) {
    if (next[key] !== original[key]) body[key] = next[key];
  }
  return body;
}

// ---------------------------------------------------------------------------
// Internal audits (slice 6)
// ---------------------------------------------------------------------------

export interface InternalAudit {
  id: number;
  /** `AU-0007` — built by the server. */
  code: string;
  title: string;
  scope_node: number;
  scope_node_name: string;
  lead_auditor: number;
  lead_auditor_name: string;
  lead_auditor_title: string;
  /** A person deactivated after being named: a quality manager replaces them. */
  lead_auditor_is_active: boolean;
  planned_on: string;
  status: AuditStatus;
  status_label: string;
  summary: string;
  cancel_reason: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  /** Derived by the server from the findings, never stored. */
  findings_total: number;
  findings_open: number;
  /** What the viewer may do right now — the very functions the endpoints enforce. `can_edit` (the plan:
   *  title, date, scope) ends when the audit starts; `can_change_auditor` lasts while it runs. */
  can_edit: boolean;
  can_change_auditor: boolean;
  can_start: boolean;
  can_complete: boolean;
  can_cancel: boolean;
  can_raise_finding: boolean;
}

export type AuditMine = "" | "auditor" | "manage";

export interface AuditFilters {
  q: string;
  status: AuditStatus | "";
  mine: AuditMine;
}

export const EMPTY_AUDIT_FILTERS: AuditFilters = { q: "", status: "", mine: "" };

export function hasActiveAuditFilters(filters: AuditFilters): boolean {
  return Boolean(filters.q.trim() || filters.status || filters.mine);
}

/** The query string of `GET /quality/audits/` — an empty filter sends nothing at all. */
export function auditQueryParams(filters: AuditFilters, page: number, pageSize: number): Record<string, string | number> {
  const params: Record<string, string | number> = { page, page_size: pageSize };
  if (filters.q.trim()) params.q = filters.q.trim();
  if (filters.status) params.status = filters.status;
  if (filters.mine) params.mine = filters.mine;
  return params;
}

/** «۳ یافته، ۱ باز» — or «بدون یافته» (a clean audit is a result, not a gap). */
export function findingsSummary(audit: Pick<InternalAudit, "findings_total" | "findings_open">): string {
  if (audit.findings_total === 0) return "بدون یافته";
  const total = `${toPersianDigits(audit.findings_total)} یافته`;
  return audit.findings_open > 0 ? `${total}، ${toPersianDigits(audit.findings_open)} باز` : total;
}

/** A planned audit whose date has passed. One already started, finished or called off is not late. */
export function auditIsLate(audit: Pick<InternalAudit, "status" | "planned_on">, today: string): boolean {
  return audit.status === "PLANNED" && audit.planned_on < today;
}

export interface AuditForm {
  title: string;
  scope_node: number | null;
  lead_auditor: number | null;
  /** ISO date. */
  planned_on: string;
}

export function emptyAuditForm(): AuditForm {
  return { title: "", scope_node: null, lead_auditor: null, planned_on: "" };
}

export function auditFormFrom(audit: InternalAudit): AuditForm {
  return {
    title: audit.title,
    scope_node: audit.scope_node,
    lead_auditor: audit.lead_auditor,
    planned_on: audit.planned_on,
  };
}

/** Early Persian messages, as for the other forms. A date in the past is refused only when it is *new* or
 *  *changed* — a late audit must stay editable (its title, its auditor) without being re-dated, which is
 *  exactly the server's rule. */
export function validateAuditForm(
  form: AuditForm,
  today: string,
  original?: Pick<InternalAudit, "planned_on">,
): Partial<Record<keyof AuditForm, string>> {
  const errors: Partial<Record<keyof AuditForm, string>> = {};
  if (!form.title.trim()) errors.title = "عنوان ممیزی را بنویسید.";
  else if (form.title.trim().length > TITLE_MAX) errors.title = `عنوان نباید بیش از ${toPersianDigits(TITLE_MAX)} نویسه باشد.`;
  if (form.scope_node === null) errors.scope_node = "گرهٔ ممیزی‌شونده را انتخاب کنید.";
  if (form.lead_auditor === null) errors.lead_auditor = "ممیز اصلی را انتخاب کنید.";
  if (!form.planned_on) errors.planned_on = "تاریخ برنامه را مشخص کنید.";
  else if (form.planned_on < today && form.planned_on !== original?.planned_on) errors.planned_on = "تاریخ برنامه نمی‌تواند در گذشته باشد.";
  return errors;
}

export function auditCreatePayload(form: AuditForm): Record<string, unknown> {
  return {
    title: form.title.trim(),
    scope_node: form.scope_node,
    lead_auditor: form.lead_auditor,
    planned_on: form.planned_on,
  };
}

/** Only what changed, so an edit that changes nothing sends nothing (and logs nothing). */
export function auditPatchPayload(audit: InternalAudit, form: AuditForm): Record<string, unknown> {
  const original = auditFormFrom(audit);
  const next = { ...form, title: form.title.trim() };
  const body: Record<string, unknown> = {};
  for (const key of Object.keys(next) as (keyof AuditForm)[]) {
    if (next[key] !== original[key]) body[key] = next[key];
  }
  return body;
}

export interface FindingForm {
  title: string;
  description: string;
  owner_node: number | null;
  severity: NcSeverity;
  /** ISO date. */
  detected_on: string;
}

/** A finding starts on the audited node, as the least severe level (an observation), found today. */
export function emptyFindingForm(scopeNode: number, today: string): FindingForm {
  return { title: "", description: "", owner_node: scopeNode, severity: "MINOR", detected_on: today };
}

export function validateFindingForm(form: FindingForm, today: string): Partial<Record<keyof FindingForm, string>> {
  const errors: Partial<Record<keyof FindingForm, string>> = {};
  if (!form.title.trim()) errors.title = "عنوان یافته را بنویسید.";
  else if (form.title.trim().length > TITLE_MAX) errors.title = `عنوان نباید بیش از ${toPersianDigits(TITLE_MAX)} نویسه باشد.`;
  if (!form.description.trim()) errors.description = "شرح یافته را بنویسید.";
  else if (form.description.trim().length > TEXT_MAX) errors.description = `شرح نباید بیش از ${toPersianDigits(TEXT_MAX)} نویسه باشد.`;
  if (form.owner_node === null) errors.owner_node = "گرهٔ مربوط را انتخاب کنید.";
  if (!form.detected_on) errors.detected_on = "تاریخ کشف را مشخص کنید.";
  else if (form.detected_on > today) errors.detected_on = "تاریخ کشف نمی‌تواند در آینده باشد.";
  return errors;
}

export function findingPayload(form: FindingForm): Record<string, unknown> {
  return {
    title: form.title.trim(),
    description: form.description.trim(),
    owner_node: form.owner_node,
    severity: form.severity,
    detected_on: form.detected_on,
  };
}

/** The node and everything beneath it, from the chart as the server sends it (depth-first, with depth):
 *  a finding may be filed against the audited node or any node under it — never above or beside. */
export function nodesWithin<T extends { id: number; depth: number }>(nodes: T[], scopeId: number): T[] {
  const start = nodes.findIndex((node) => node.id === scopeId);
  if (start === -1) return [];
  const end = nodes.findIndex((node, index) => index > start && node.depth <= nodes[start].depth);
  return nodes.slice(start, end === -1 ? undefined : end);
}

// ---------------------------------------------------------------------------
// The risk register (slice 8)
// ---------------------------------------------------------------------------

export type RiskStatus = "IDENTIFIED" | "MITIGATING" | "ACCEPTED" | "CLOSED";
export type RiskLevel = "low" | "medium" | "high" | "critical";

export const RISK_STATUS_LABELS: Record<RiskStatus, string> = {
  IDENTIFIED: "شناسایی‌شده",
  MITIGATING: "در حال کاهش",
  ACCEPTED: "پذیرفته‌شده",
  CLOSED: "بسته‌شده",
};

export const RISK_STATUS_TONE: Record<RiskStatus, QualityTone> = {
  IDENTIFIED: "warning",
  MITIGATING: "brand",
  ACCEPTED: "info",
  CLOSED: "neutral",
};

/** The mirror of `RISK_LEVELS` in the server's `quality/queries.py` — the one place the bands are
 *  defined there. The server sends `level` with every risk; this serves the form's live preview and the
 *  heat map's colours, where there is no row yet. A test pins both to the same table. */
export const RISK_LEVELS: { level: RiskLevel; low: number; high: number }[] = [
  { level: "low", low: 1, high: 4 },
  { level: "medium", low: 5, high: 9 },
  { level: "high", low: 10, high: 14 },
  { level: "critical", low: 15, high: 25 },
];

export const RISK_LEVEL_LABELS: Record<RiskLevel, string> = {
  low: "کم",
  medium: "متوسط",
  high: "زیاد",
  critical: "بحرانی",
};

/** Green → amber → orange → red: `cell` for the heat map, `chip` for a badge beside a title. */
export const RISK_LEVEL_STYLE: Record<RiskLevel, { cell: string; chip: string }> = {
  low: { cell: "bg-emerald-100 text-emerald-900", chip: "bg-emerald-50 text-emerald-800 ring-emerald-600/20" },
  medium: { cell: "bg-amber-100 text-amber-900", chip: "bg-amber-50 text-amber-800 ring-amber-600/20" },
  high: { cell: "bg-orange-200 text-orange-950", chip: "bg-orange-50 text-orange-800 ring-orange-600/20" },
  critical: { cell: "bg-rose-200 text-rose-950", chip: "bg-rose-50 text-rose-800 ring-rose-600/20" },
};

export const LIKELIHOOD_LABELS: Record<number, string> = { 1: "بسیار کم", 2: "کم", 3: "متوسط", 4: "زیاد", 5: "بسیار زیاد" };
export const IMPACT_LABELS: Record<number, string> = { 1: "ناچیز", 2: "کم", 3: "متوسط", 4: "شدید", 5: "بحرانی" };
export const RISK_SCALE = [1, 2, 3, 4, 5] as const;

export function riskLevel(score: number): RiskLevel {
  const band = RISK_LEVELS.find(({ low, high }) => low <= score && score <= high);
  if (!band) throw new RangeError(`a risk score is 1-25, not ${score}`);
  return band.level;
}

/** «۳×۴ = ۱۲» */
export function assessmentText(likelihood: number, impact: number): string {
  return toPersianDigits(`${likelihood}×${impact} = ${likelihood * impact}`);
}

export interface RiskItem {
  id: number;
  /** `RK-0013` — built by the server. */
  code: string;
  title: string;
  description: string;
  owner_node: number;
  owner_node_name: string;
  owner: number | null;
  owner_name: string | null;
  owner_title: string | null;
  owner_is_active: boolean | null;
  created_by: number;
  created_by_name: string;
  likelihood: number;
  impact: number;
  /** Derived by the server (likelihood × impact), never stored. */
  score: number;
  level: RiskLevel;
  level_label: string;
  status: RiskStatus;
  status_label: string;
  mitigation_plan: string;
  review_on: string | null;
  /** Still on the register and its review date has passed. */
  review_overdue: boolean;
  created_at: string;
  updated_at: string;
  /** `manage_quality`, or a lead of the node or one above it — the function the PATCH enforces. */
  can_edit: boolean;
}

export interface MatrixCell {
  likelihood: number;
  impact: number;
  score: number;
  level: RiskLevel;
  count: number;
}

export interface RiskMatrix {
  cells: MatrixCell[];
  total: number;
  levels: Record<RiskLevel, number>;
}

/** The heat map's 5×5 grid: the most likely row on top, impact growing along each row. Built from
 *  whatever order the cells arrive in, and a missing cell is a zero rather than a hole. */
export function matrixRows(cells: MatrixCell[]): MatrixCell[][] {
  const at = new Map(cells.map((cell) => [`${cell.likelihood}:${cell.impact}`, cell]));
  return [5, 4, 3, 2, 1].map((likelihood) =>
    [1, 2, 3, 4, 5].map(
      (impact) =>
        at.get(`${likelihood}:${impact}`) ?? {
          likelihood, impact, score: likelihood * impact, level: riskLevel(likelihood * impact), count: 0,
        },
    ),
  );
}

export type RiskMine = "" | "owner" | "created" | "manage";

export interface RiskFilters {
  q: string;
  status: RiskStatus | "";
  level: RiskLevel | "";
  mine: RiskMine;
  reviewDue: boolean;
  /** A heat-map cell picked as a filter (both set, or both null). */
  likelihood: number | null;
  impact: number | null;
}

export const EMPTY_RISK_FILTERS: RiskFilters = { q: "", status: "", level: "", mine: "", reviewDue: false, likelihood: null, impact: null };

export function hasActiveRiskFilters(filters: RiskFilters): boolean {
  return Boolean(
    filters.q.trim() || filters.status || filters.level || filters.mine || filters.reviewDue || filters.likelihood !== null || filters.impact !== null,
  );
}

/** The query string of `GET /quality/risks/` — an empty filter sends nothing at all. */
export function riskQueryParams(filters: RiskFilters, page: number, pageSize: number): Record<string, string | number> {
  const params: Record<string, string | number> = { page, page_size: pageSize };
  if (filters.q.trim()) params.q = filters.q.trim();
  if (filters.status) params.status = filters.status;
  if (filters.level) params.level = filters.level;
  if (filters.mine) params.mine = filters.mine;
  if (filters.reviewDue) params.review = "due";
  if (filters.likelihood !== null) params.likelihood = filters.likelihood;
  if (filters.impact !== null) params.impact = filters.impact;
  return params;
}

/** The nodes this person may file a risk against — the server's rule (`manage_quality`, or a lead of the
 *  node or one above it) from what `/auth/me/` says. A temporary cover (Phase 16) is not in that answer,
 *  so a delegate files through the server's own check only. */
export function manageableNodes<T extends { id: number; depth: number }>(
  nodes: T[],
  memberships: { node: number; is_lead: boolean }[] | undefined,
  managesQuality: boolean,
): T[] {
  if (managesQuality) return nodes;
  const ids = new Set<number>();
  for (const membership of memberships ?? []) {
    if (membership.is_lead) for (const node of nodesWithin(nodes, membership.node)) ids.add(node.id);
  }
  return nodes.filter((node) => ids.has(node.id));
}

export interface RiskForm {
  title: string;
  description: string;
  owner_node: number | null;
  owner: number | null;
  likelihood: number;
  impact: number;
  mitigation_plan: string;
  /** ISO date, or "" for none. */
  review_on: string;
  /** Sent only by an edit. */
  status: RiskStatus;
}

export function emptyRiskForm(ownerNode: number | null): RiskForm {
  return {
    title: "", description: "", owner_node: ownerNode, owner: null, likelihood: 3, impact: 3,
    mitigation_plan: "", review_on: "", status: "IDENTIFIED",
  };
}

export function riskFormFrom(risk: RiskItem): RiskForm {
  return {
    title: risk.title,
    description: risk.description,
    owner_node: risk.owner_node,
    owner: risk.owner,
    likelihood: risk.likelihood,
    impact: risk.impact,
    mitigation_plan: risk.mitigation_plan,
    review_on: risk.review_on ?? "",
    status: risk.status,
  };
}

const inScale = (value: number) => Number.isInteger(value) && value >= 1 && value <= 5;

/** Early Persian messages; the server re-checks everything. A past review date is refused only when it is
 *  new or changed (the server's rule), and no date at all is fine. */
export function validateRiskForm(
  form: RiskForm,
  today: string,
  original?: Pick<RiskItem, "review_on">,
): Partial<Record<keyof RiskForm, string>> {
  const errors: Partial<Record<keyof RiskForm, string>> = {};
  if (!form.title.trim()) errors.title = "عنوان ریسک را بنویسید.";
  else if (form.title.trim().length > TITLE_MAX) errors.title = `عنوان نباید بیش از ${toPersianDigits(TITLE_MAX)} نویسه باشد.`;
  if (!form.description.trim()) errors.description = "شرح ریسک را بنویسید.";
  else if (form.description.trim().length > TEXT_MAX) errors.description = `شرح نباید بیش از ${toPersianDigits(TEXT_MAX)} نویسه باشد.`;
  if (form.mitigation_plan.trim().length > TEXT_MAX) errors.mitigation_plan = `برنامه نباید بیش از ${toPersianDigits(TEXT_MAX)} نویسه باشد.`;
  if (form.owner_node === null) errors.owner_node = "گرهٔ مربوط را انتخاب کنید.";
  if (!inScale(form.likelihood)) errors.likelihood = "احتمال را از ۱ تا ۵ انتخاب کنید.";
  if (!inScale(form.impact)) errors.impact = "اثر را از ۱ تا ۵ انتخاب کنید.";
  if (form.review_on && form.review_on < today && form.review_on !== (original?.review_on ?? ""))
    errors.review_on = "تاریخ بازنگری نمی‌تواند در گذشته باشد.";
  return errors;
}

export function riskCreatePayload(form: RiskForm): Record<string, unknown> {
  return {
    title: form.title.trim(),
    description: form.description.trim(),
    owner_node: form.owner_node,
    owner: form.owner,
    likelihood: form.likelihood,
    impact: form.impact,
    mitigation_plan: form.mitigation_plan.trim(),
    review_on: form.review_on || null,
  };
}

/** Only what changed, so an edit that changes nothing sends nothing (and logs nothing). Clearing the owner
 *  or the review date is a change, sent as null. */
export function riskPatchPayload(risk: RiskItem, form: RiskForm): Record<string, unknown> {
  const original = riskFormFrom(risk);
  const next: RiskForm = {
    ...form,
    title: form.title.trim(),
    description: form.description.trim(),
    mitigation_plan: form.mitigation_plan.trim(),
  };
  const body: Record<string, unknown> = {};
  for (const key of Object.keys(next) as (keyof RiskForm)[]) {
    if (next[key] !== original[key]) body[key] = key === "review_on" ? next.review_on || null : next[key];
  }
  return body;
}
