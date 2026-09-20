/**
 * History screen helpers (Phase 6): query building and the filter vocabularies.
 * Pure functions, no fetching — relative imports only (vitest has no `@/` alias).
 */
import type { DocumentEventKind, DocumentGroup, DocumentStatus } from "./types";

export type HistoryTab = "revisions" | "activity";

export interface RevisionFilters {
  search: string;
  group: DocumentGroup | "";
  status: DocumentStatus | "";
  /** A document family such as "PR-01": its whole revision chain. */
  family: string;
}

export interface ActivityFilters {
  kind: DocumentEventKind | "";
  /** Only the last N days; "" = all time. */
  days: string;
  q: string;
  actor: string;
}

export const EMPTY_REVISION_FILTERS: RevisionFilters = { search: "", group: "", status: "", family: "" };
export const EMPTY_ACTIVITY_FILTERS: ActivityFilters = { kind: "", days: "", q: "", actor: "" };

export const EVENT_KIND_LABELS: Record<DocumentEventKind, string> = {
  submitted: "ارسال برای تایید",
  confirmed: "تایید شد",
  approved: "تصویب شد",
  returned: "مرجوع شد",
  superseded: "منسوخ شد (جایگزین شد)",
  imported: "وارد شده از نسخهٔ ۱",
};

/** Tailwind classes per event kind (a dot in the feed). */
export const EVENT_KIND_TONE: Record<DocumentEventKind, string> = {
  submitted: "bg-blue-500",
  confirmed: "bg-amber-500",
  approved: "bg-green-600",
  returned: "bg-red-500",
  superseded: "bg-slate-400",
  imported: "bg-violet-400",
};

export const ACTIVITY_WINDOWS: { value: string; label: string }[] = [
  { value: "", label: "همه زمان‌ها" },
  { value: "7", label: "۷ روز اخیر" },
  { value: "30", label: "۳۰ روز اخیر" },
  { value: "90", label: "۹۰ روز اخیر" },
];

/** Drops empty values so the URL carries only real filters. */
function compact(params: Record<string, string | number>): Record<string, string | number> {
  return Object.fromEntries(Object.entries(params).filter(([, value]) => value !== "" && value !== undefined));
}

export function revisionParams(filters: RevisionFilters, page: number, pageSize: number) {
  return compact({
    page,
    page_size: pageSize,
    search: filters.search.trim(),
    group: filters.group,
    status: filters.status,
    family: filters.family,
  });
}

export function activityParams(filters: ActivityFilters, page: number, pageSize: number) {
  return compact({
    page,
    page_size: pageSize,
    kind: filters.kind,
    days: filters.days,
    q: filters.q.trim(),
    actor: filters.actor.trim(),
  });
}

/** True when any filter narrows the list (drives the «پاک کردن فیلترها» link). */
export function hasActiveFilters(filters: RevisionFilters | ActivityFilters): boolean {
  return Object.values(filters).some((value) => value !== "");
}
