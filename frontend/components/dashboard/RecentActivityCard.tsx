"use client";

import Link from "next/link";
import { Activity, ArrowLeft } from "lucide-react";
import { Code } from "@/components/Code";
import { ErrorBanner } from "@/components/StatusBanner";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { SkeletonLines } from "@/components/ui/Skeleton";
import { EVENT_KIND_TONE } from "@/lib/history";
import { formatJalaliDateTime } from "@/lib/jalali";
import { useApiQuery } from "@/lib/use-api-query";
import type { ActivityEvent, Paginated } from "@/lib/types";

/** The last 10 workflow events across all documents; the full feed is on the History screen. */
export function RecentActivityCard() {
  const { data, error, loading } = useApiQuery<Paginated<ActivityEvent>>("/history/activity/?page_size=10");

  return (
    <Card aria-label="فعالیت‌های اخیر">
      <CardHeader
        title="فعالیت‌های اخیر"
        icon={<Activity />}
        actions={
          <Link
            href="/documents/history"
            className="group inline-flex items-center gap-1 text-sm text-brand-700 transition-colors hover:text-brand-800"
          >
            همهٔ سوابق
            <ArrowLeft className="size-4 transition-transform duration-200 group-hover:-translate-x-0.5" />
          </Link>
        }
      />

      {loading && !data && <SkeletonLines rows={4} />}
      {error && <ErrorBanner message={error} />}
      {data && data.results.length === 0 && <EmptyState compact message="هنوز فعالیتی ثبت نشده است." />}

      {data && data.results.length > 0 && (
        // A timeline: a thin rail joins the events' dots.
        <ol className="relative space-y-4 before:absolute before:inset-y-2 before:right-[4.5px] before:w-px before:bg-slate-200">
          {data.results.map((event) => (
            <li key={event.id} className="relative flex gap-3 text-sm">
              <span
                aria-hidden
                className={`relative mt-2 size-2.5 shrink-0 rounded-full ring-4 ring-white ${EVENT_KIND_TONE[event.kind]}`}
              />
              <div className="min-w-0 flex-1">
                <p className="text-slate-900">
                  <span className="font-bold">{event.kind_label}</span>
                  <span className="text-slate-500"> — {event.actor_name}</span>
                </p>
                <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-slate-600">
                  <Code>{event.document.full_code}</Code>
                  <Link
                    href={`/documents/${event.document.id}/edit`}
                    className="truncate transition-colors hover:text-brand-700"
                  >
                    {event.document.title}
                  </Link>
                </p>
                {event.reason && (
                  <p className="mt-1 truncate rounded-lg bg-slate-50 px-2.5 py-1 text-slate-500" title={event.reason}>
                    {event.reason}
                  </p>
                )}
              </div>
              <time className="shrink-0 pt-0.5 text-xs text-slate-400" dateTime={event.created_at}>
                {formatJalaliDateTime(event.created_at)}
              </time>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
