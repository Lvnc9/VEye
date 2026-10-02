/** The «گزارش‌ها» screen's pure logic (Phase 17): which URL an export button calls, and how the company
 *  numbers are typed and said. All fetching and saving lives in the components; this is what can be
 *  tested without a network. */

import { toPersianDigits } from "./jalali";

export interface DocumentExportFilters {
  group?: string;
  category?: string;
  status?: string;
  search?: string;
}

/** `/reports/documents/export/` with only the filters that are set — an empty value is "no filter",
 *  never `?group=` (the register's own filters treat an unknown value as matching nothing). */
export function documentsExportPath(filters: DocumentExportFilters = {}): string {
  const params = new URLSearchParams();
  for (const key of ["group", "category", "status", "search"] as const) {
    const value = filters[key]?.trim();
    if (value) params.set(key, value);
  }
  const query = params.toString();
  return `/reports/documents/export/${query ? `?${query}` : ""}`;
}

export function projectsExportPath(archived = false): string {
  return `/reports/projects/export/${archived ? "?archived=1" : ""}`;
}

// ---------------------------------------------------------------------------
// The company numbers (`GET /reports/kpi/`). The server computes them; this is only what the screen
// needs to type and to say them — in Persian digits, in the unit a person would use.
// ---------------------------------------------------------------------------

export interface StepSummary {
  count: number;
  average_days: number | null;
  median_days: number | null;
  longest_days: number | null;
}

export interface WaitingNow {
  count: number;
  oldest_days: number | null;
}

export interface WorkloadRow {
  user: number;
  name: string;
  open: number;
  overdue: number;
}

export interface KpiResponse {
  days: number;
  documents: {
    confirm_step: StepSummary;
    approve_step: StepSummary;
    returns: { confirmed: number; approved: number; returned: number; decisions: number; rate: number | null };
    waiting_now: { confirmation: WaitingNow; approval: WaitingNow };
    submitted_in_window: number;
  };
  projects: {
    scope_note: string;
    unfinished_count: number;
    by_status: Record<string, number>;
    progress: number | null;
    weight_done: number;
    weight_total: number;
    overdue_objectives: number;
    projects_with_overdue: number;
    workload: WorkloadRow[];
  };
}

/** The look-back windows offered for the document numbers (the server accepts 7–730). */
export const KPI_DAYS_OPTIONS = [30, 90, 180, 365] as const;

export function kpiPath(days: number): string {
  return `/reports/kpi/?days=${days}`;
}

const DASH = "—";

/** "۲٫۵ روز", "۶ ساعت", "کمتر از یک ساعت" — a duration given in days, in the unit that reads best. */
export function formatDuration(days: number | null | undefined): string {
  if (days === null || days === undefined) return DASH;
  const hours = days * 24;
  if (hours < 1) return "کمتر از یک ساعت";
  if (days < 1) return `${toPersianDigits(Math.round(hours))} ساعت`;
  const rounded = Math.round(days * 10) / 10;
  return `${toPersianDigits(String(rounded).replace(".", "٫"))} روز`;
}

/** "۱۴٫۳٪" — a percentage, or a dash when there was nothing to measure (never a misleading ۰٪). */
export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return DASH;
  return `${toPersianDigits(String(value).replace(".", "٫"))}٪`;
}

/** A workload bar's width as a percentage of the busiest person's open count. */
export function workloadWidth(open: number, busiest: number): number {
  return busiest > 0 ? Math.round((100 * open) / busiest) : 0;
}
