/**
 * «تقویم» (Phase 22): the shape `GET /agenda/` answers with and the pure logic of laying a month out.
 * Relative imports only (vitest has no `@/` alias).
 */
import { jalaliMonthGrid, jalaliMonthLength, jalaliToIso } from "./jalali";

export type AgendaKind =
  | "objective"
  | "action"
  | "meeting"
  | "audit"
  | "risk_review"
  | "document_review"
  | "leave"
  | "delegation"
  | "team_leave"
  | "holiday";

export interface AgendaItem {
  key: string;
  kind: AgendaKind;
  kind_label: string;
  /** ISO date; the first day for a span. */
  date: string;
  /** ISO date of a span's last day (leave, a delegation), else null. */
  end_date: string | null;
  title: string;
  subtitle: string;
  url: string;
  overdue: boolean;
}

export interface AgendaResponse {
  from: string;
  to: string;
  is_lead: boolean;
  team: boolean;
  items: AgendaItem[];
}

/** A dot/chip colour per kind (Tailwind classes; the calendar reads on light and dark). */
export const AGENDA_TONE: Record<AgendaKind, { dot: string; chip: string }> = {
  objective: { dot: "bg-sky-500", chip: "bg-sky-50 text-sky-900 dark:bg-sky-400/10 dark:text-sky-200" },
  action: { dot: "bg-orange-500", chip: "bg-orange-50 text-orange-900 dark:bg-orange-400/10 dark:text-orange-200" },
  meeting: { dot: "bg-violet-500", chip: "bg-violet-50 text-violet-900 dark:bg-violet-400/10 dark:text-violet-200" },
  audit: { dot: "bg-indigo-500", chip: "bg-indigo-50 text-indigo-900 dark:bg-indigo-400/10 dark:text-indigo-200" },
  risk_review: { dot: "bg-rose-500", chip: "bg-rose-50 text-rose-900 dark:bg-rose-400/10 dark:text-rose-200" },
  document_review: { dot: "bg-teal-500", chip: "bg-teal-50 text-teal-900 dark:bg-teal-400/10 dark:text-teal-200" },
  leave: { dot: "bg-emerald-500", chip: "bg-emerald-50 text-emerald-900 dark:bg-emerald-400/10 dark:text-emerald-200" },
  delegation: { dot: "bg-amber-500", chip: "bg-amber-50 text-amber-900 dark:bg-amber-400/10 dark:text-amber-200" },
  team_leave: { dot: "bg-lime-600", chip: "bg-lime-50 text-lime-900 dark:bg-lime-400/10 dark:text-lime-200" },
  holiday: { dot: "bg-slate-400", chip: "bg-slate-100 text-slate-700 dark:bg-slate-400/10 dark:text-slate-300" },
};

export interface MonthDay {
  /** Jalali day of month, or null for padding cells. */
  day: number | null;
  iso: string | null;
}

/** The month as whole Saturday-first weeks, each cell with its ISO date. */
export function monthCells(jy: number, jm: number): MonthDay[] {
  return jalaliMonthGrid(jy, jm).map((day) => ({ day, iso: day === null ? null : jalaliToIso(jy, jm, day) }));
}

/** First and last ISO day of a Jalali month — the window to ask `/agenda/` for. */
export function monthWindow(jy: number, jm: number): { from: string; to: string } {
  return { from: jalaliToIso(jy, jm, 1), to: jalaliToIso(jy, jm, jalaliMonthLength(jy, jm)) };
}

function addIsoDays(iso: string, days: number): string {
  const date = new Date(`${iso}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

/**
 * Items by day for the window: a single-day item sits on its date; a span (leave, cover) is repeated on
 * every day it covers, clipped to the window. Items keep the server's order within a day.
 */
export function itemsByDay(items: AgendaItem[], from: string, to: string): Record<string, AgendaItem[]> {
  const days: Record<string, AgendaItem[]> = {};
  for (const item of items) {
    const last = item.end_date && item.end_date > item.date ? item.end_date : item.date;
    let day = item.date < from ? from : item.date;
    const stop = last > to ? to : last;
    while (day <= stop) {
      (days[day] ??= []).push(item);
      day = addIsoDays(day, 1);
    }
  }
  return days;
}

/** How many items to draw as chips in a day cell before «+n». */
export const CHIPS_PER_DAY = 3;
