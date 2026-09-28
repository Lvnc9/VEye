"use client";

import Link from "next/link";
import { useState } from "react";
import { Code } from "@/components/Code";
import { Pager } from "@/components/Pager";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
import { Activity, ArrowLeft, RotateCcw, SearchX } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { selectClass } from "@/components/ui/Field";
import { cx } from "@/components/ui/cx";

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
const select = cx(selectClass, "min-w-[8rem] flex-1 sm:flex-none");

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
      <Card as="section" className="flex flex-wrap items-center gap-2 p-3 sm:gap-3 sm:p-4">
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
          className="w-full sm:w-44"
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
          <Button
            variant="ghost"
            size="sm"
            icon={<RotateCcw />}
            className="animate-fade-in"
            onClick={() => {
              onFilters(EMPTY_ACTIVITY_FILTERS);
              setResetKey((n) => n + 1);
              setPage(1);
            }}
          >
            پاک کردن فیلترها
          </Button>
        )}
        <span className="ms-auto rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-600 tabular-nums">
          {count} رویداد
        </span>
      </Card>

      {error && <ErrorBanner message={error} />}
      {loading && rows.length === 0 && <LoadingBanner />}
      {!error && !loading && rows.length === 0 && (
        <EmptyState
          icon={hasActiveFilters(filters) ? <SearchX /> : <Activity />}
          message={hasActiveFilters(filters) ? "رویدادی با این مشخصات یافت نشد." : "هنوز فعالیتی ثبت نشده است."}
        />
      )}

      {rows.length > 0 && (
        <Card
          as="div"
          flush
          className={cx("overflow-hidden transition-opacity duration-200", loading && "opacity-60")}
        >
        <ol className="divide-y divide-slate-100">
          {rows.map((event) => (
            <li key={event.id} className="flex gap-3 px-4 py-3.5 text-sm transition-colors hover:bg-slate-50/70 sm:px-5">
              <span
                aria-hidden
                className={`mt-2 size-2.5 shrink-0 rounded-full ring-4 ring-slate-100 ${EVENT_KIND_TONE[event.kind]}`}
              />
              <div className="min-w-0 flex-1">
                <p className="text-slate-900">
                  <span className="font-bold">{event.kind_label}</span>
                  <span className="text-slate-500">
                    {" "}
                    — {event.actor_name}
                    {event.actor_title ? ` (${event.actor_title})` : ""}
                  </span>
                </p>
                <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-slate-600">
                  <button
                    type="button"
                    title="نمایش همهٔ بازنگری‌های این مستند"
                    onClick={() => onOpenFamily(event.document.full_code.split("-").slice(0, 2).join("-"))}
                    className="rounded-md transition-transform hover:scale-105"
                  >
                    <Code>{event.document.full_code}</Code>
                  </button>
                  <Link
                    href={`/documents/${event.document.id}/edit`}
                    className="truncate transition-colors hover:text-brand-700"
                  >
                    {event.document.title}
                  </Link>
                  <span className="inline-flex items-center gap-1 text-xs text-slate-400">
                    {event.from_status_label}
                    <ArrowLeft className="size-3" aria-label="به" />
                    {event.to_status_label}
                  </span>
                </p>
                {event.reason && (
                  <p className="mt-1.5 whitespace-pre-wrap rounded-lg bg-slate-50 px-3 py-1.5 text-slate-700">{event.reason}</p>
                )}
              </div>
              <time className="shrink-0 text-xs text-slate-400" dateTime={event.created_at}>
                {formatJalaliDateTime(event.created_at)}
              </time>
            </li>
          ))}
        </ol>
        </Card>
      )}

      <Pager page={Math.min(page, totalPages)} totalPages={totalPages} onChange={setPage} />
    </div>
  );
}
