/**
 * The quality module's data model and pure logic (Phase 18): non-conformances, their corrective
 * actions and the history. No fetching here — what can be tested without a network, so the screens
 * stay thin. Relative imports only (vitest has no `@/` alias).
 */

import { formatJalali, toPersianDigits } from "./jalali";

export type NcSource = "AUDIT" | "COMPLAINT" | "INSPECTION" | "INTERNAL" | "OTHER";
export type NcSeverity = "MINOR" | "MAJOR" | "CRITICAL";
export type NcStatus = "OPEN" | "IN_PROGRESS" | "CLOSED" | "REJECTED";
export type ActionStatus = "TODO" | "IN_PROGRESS" | "DONE" | "VERIFIED" | "CANCELLED";

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
};

/** The second line of a history entry — what the kind alone does not say: a before → after, a deadline
 *  moving, or the reason someone typed. Empty when the kind label says it all. */
export function qualityEventDetail(event: QualityEvent): string {
  if (event.kind === "action_due_changed") {
    return `${formatJalali(event.from_status)} ← ${formatJalali(event.to_status)}`;
  }
  if (event.kind === "action_assigned") return event.note;
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
