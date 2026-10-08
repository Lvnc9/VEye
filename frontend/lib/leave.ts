/**
 * Leave requests (Phase 19): the vocabulary and the pure logic of the «مرخصی» screen. No fetching here.
 * Relative imports only (vitest has no `@/` alias).
 */

import { toPersianDigits } from "./jalali";

export type LeaveType = "ANNUAL" | "SICK" | "UNPAID";
export type LeaveStatus = "PENDING" | "APPROVED" | "REJECTED" | "CANCELLED";

export const LEAVE_TYPE_LABELS: Record<LeaveType, string> = { ANNUAL: "استحقاقی", SICK: "استعلاجی", UNPAID: "بدون حقوق" };

export const LEAVE_STATUS_LABELS: Record<LeaveStatus, string> = {
  PENDING: "منتظر تایید",
  APPROVED: "تایید شد",
  REJECTED: "رد شد",
  CANCELLED: "لغو شد",
};

export const LEAVE_STATUS_TONE: Record<LeaveStatus, "neutral" | "brand" | "success" | "warning" | "danger" | "info" | "violet"> = {
  PENDING: "warning",
  APPROVED: "success",
  REJECTED: "danger",
  CANCELLED: "neutral",
};

export interface LeaveRequest {
  id: number;
  requester: number;
  requester_name: string;
  requester_title: string;
  node: number | null;
  node_name: string;
  leave_type: LeaveType;
  leave_type_label: string;
  starts_on: string;
  ends_on: string;
  /** Calendar days, both ends included — derived by the server. */
  days: number;
  reason: string;
  status: LeaveStatus;
  status_label: string;
  decided_by_name: string;
  decided_at: string | null;
  decision_note: string;
  cancelled_at: string | null;
  created_at: string;
  /** The rules the endpoints enforce: a pending request of someone under you (never your own). */
  can_decide: boolean;
  /** Yours, and pending — or approved and not begun. */
  can_cancel: boolean;
}

/** Days off between two ISO dates, both included; null while incomplete or out of order. */
export function inclusiveDays(startsOn: string, endsOn: string): number | null {
  if (!startsOn || !endsOn) return null;
  const start = Date.parse(`${startsOn}T00:00:00Z`);
  const end = Date.parse(`${endsOn}T00:00:00Z`);
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return null;
  return Math.round((end - start) / 86_400_000) + 1;
}

export function daysText(days: number): string {
  return `${toPersianDigits(days)} روز`;
}

export type LeaveTab = "mine" | "decide" | "all";

/** The tabs a person sees: their own requests always; «منتظر تصمیم من» for a مسئول or the مدیر عامل;
 *  «همه» for HR (`manage_personnel`) and the مدیر عامل. (A temporary cover is not in `/auth/me/`: a
 *  delegate decides from the notification's link, and the server lets them.) */
export function leaveTabs({ leads, top, hr }: { leads: boolean; top: boolean; hr: boolean }): LeaveTab[] {
  const tabs: LeaveTab[] = ["mine"];
  if (leads || top) tabs.push("decide");
  if (hr || top) tabs.push("all");
  return tabs;
}

export function leaveQueryParams(tab: LeaveTab, status: LeaveStatus | "", page: number, pageSize: number): Record<string, string | number> {
  const params: Record<string, string | number> = { page, page_size: pageSize };
  if (tab === "mine") params.mine = 1;
  if (tab === "decide") params.to_decide = 1;
  if (status) params.status = status;
  return params;
}

export const REASON_MAX = 2000;

export interface LeaveForm {
  leave_type: LeaveType;
  /** ISO dates. */
  starts_on: string;
  ends_on: string;
  reason: string;
}

export function emptyLeaveForm(): LeaveForm {
  return { leave_type: "ANNUAL", starts_on: "", ends_on: "", reason: "" };
}

export function validateLeaveForm(form: LeaveForm): Partial<Record<keyof LeaveForm, string>> {
  const errors: Partial<Record<keyof LeaveForm, string>> = {};
  if (!form.starts_on) errors.starts_on = "روز شروع را مشخص کنید.";
  if (!form.ends_on) errors.ends_on = "روز پایان را مشخص کنید.";
  else if (form.starts_on && form.ends_on < form.starts_on) errors.ends_on = "روز پایان نمی‌تواند پیش از روز شروع باشد.";
  if (form.reason.trim().length > REASON_MAX) errors.reason = `توضیح نباید بیش از ${toPersianDigits(REASON_MAX)} نویسه باشد.`;
  return errors;
}

export function leavePayload(form: LeaveForm): Record<string, unknown> {
  return { leave_type: form.leave_type, starts_on: form.starts_on, ends_on: form.ends_on, reason: form.reason.trim() };
}
