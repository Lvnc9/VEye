"use client";

import Link from "next/link";
import { useState } from "react";
import { Code } from "@/components/Code";
import { Pager } from "@/components/Pager";
import { EmptyBanner, ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
import { DebouncedInput } from "@/components/history/DebouncedInput";
import {
  ACTIVITY_WINDOWS,
  EMPTY_ACTIVITY_FILTERS,
  EVENT_KIND_LABELS,
  EVENT_KIND_TONE,
  activityParams,
  hasActiveFilters,
  type ActivityFilters,
} from "@/lib/history";
import { formatJalaliDateTime } from "@/lib/jalali";
import { usePagedQuery } from "@/lib/use-paged-query";
import type { ActivityEvent, DocumentEventKind } from "@/lib/types";

const PAGE_SIZE = 25;
const select = "rounded border border-slate-300 bg-white px-3 py-2 text-sm";

/** The audit trail across all documents (سوابق مستندات ← فعالیت‌ها), newest first. */
export function ActivityTab({
  filters,
  onFilters,
  onOpenFamily,
}: {
  filters: ActivityFilters;
  onFilters: (filters: ActivityFilters) => void;
  /** Jump to the revisions tab narrowed to one document's family, e.g. "PR-01". */
  onOpenFamily: (family: string) => void;
}) {
  const [page, setPage] = useState(1);
  const [resetKey, setResetKey] = useState(0);
  const { rows, count, error, loading } = usePagedQuery<ActivityEvent>(
    "/history/activity/",
    activityParams(filters, page, PAGE_SIZE),
  );
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  function update(patch: Partial<ActivityFilters>) {
    onFilters({ ...filters, ...patch });
    setPage(1);
  }

  return (
    <div className="space-y-4">
      <section className="flex flex-wrap items-center gap-3">
        <DebouncedInput
          key={`q${resetKey}`}
          value={filters.q}
          onCommit={(q) => update({ q })}
          placeholder="عنوان یا کد مستند"
          ariaLabel="جست و جوی مستند"
        />
        <DebouncedInput
          key={`a${resetKey}`}
          value={filters.actor}
          onCommit={(actor) => update({ actor })}
          placeholder="نام شخص"
          ariaLabel="نام شخص"
          className="w-40 rounded border border-slate-300 bg-white px-3 py-2 text-sm"
        />
        <select
          aria-label="نوع فعالیت"
          value={filters.kind}
          onChange={(e) => update({ kind: e.target.value as DocumentEventKind | "" })}
          className={select}
        >
          <option value="">همهٔ فعالیت‌ها</option>
          {(Object.keys(EVENT_KIND_LABELS) as DocumentEventKind[]).map((value) => (
            <option key={value} value={value}>
              {EVENT_KIND_LABELS[value]}
            </option>
          ))}
        </select>
        <select
          aria-label="بازهٔ زمانی"
          value={filters.days}
          onChange={(e) => update({ days: e.target.value })}
          className={select}
        >
          {ACTIVITY_WINDOWS.map((window) => (
            <option key={window.value} value={window.value}>
              {window.label}
            </option>
          ))}
        </select>
        {hasActiveFilters(filters) && (
          <button
            type="button"
            onClick={() => {
              onFilters(EMPTY_ACTIVITY_FILTERS);
              setResetKey((n) => n + 1);
              setPage(1);
            }}
            className="text-sm text-slate-600 underline"
          >
            پاک کردن فیلترها
          </button>
        )}
        <span className="ms-auto text-sm text-slate-500">{count} رویداد</span>
      </section>

      {error && <ErrorBanner message={error} />}
      {loading && rows.length === 0 && <LoadingBanner />}
      {!error && !loading && rows.length === 0 && (
        <EmptyBanner message={hasActiveFilters(filters) ? "رویدادی با این مشخصات یافت نشد." : "هنوز فعالیتی ثبت نشده است."} />
      )}

      {rows.length > 0 && (
        <ol className={`divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white ${loading ? "opacity-60" : ""}`}>
          {rows.map((event) => (
            <li key={event.id} className="flex gap-3 px-4 py-3 text-sm">
              <span aria-hidden className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${EVENT_KIND_TONE[event.kind]}`} />
              <div className="min-w-0 flex-1">
                <p className="text-slate-900">
                  <span className="font-medium">{event.kind_label}</span>
                  <span className="text-slate-500">
                    {" "}
                    — {event.actor_name}
                    {event.actor_title ? ` (${event.actor_title})` : ""}
                  </span>
                </p>
                <p className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-slate-600">
                  <button
                    type="button"
                    title="نمایش همهٔ بازنگری‌های این مستند"
                    onClick={() => onOpenFamily(event.document.full_code.split("-").slice(0, 2).join("-"))}
                    className="underline decoration-dotted"
                  >
                    <Code>{event.document.full_code}</Code>
                  </button>
                  <Link href={`/documents/${event.document.id}/edit`} className="truncate hover:underline">
                    {event.document.title}
                  </Link>
                  <span className="text-xs text-slate-400">
                    {event.from_status_label} ← {event.to_status_label}
                  </span>
                </p>
                {event.reason && <p className="mt-1 whitespace-pre-wrap text-slate-700">{event.reason}</p>}
              </div>
              <time className="shrink-0 text-xs text-slate-400" dateTime={event.created_at}>
                {formatJalaliDateTime(event.created_at)}
              </time>
            </li>
          ))}
        </ol>
      )}

      <Pager page={Math.min(page, totalPages)} totalPages={totalPages} onChange={setPage} />
    </div>
  );
}
