"use client";

import Link from "next/link";
import { Code } from "@/components/Code";
import { EVENT_KIND_TONE } from "@/lib/history";
import { formatJalaliDateTime } from "@/lib/jalali";
import { useApiQuery } from "@/lib/use-api-query";
import type { ActivityEvent, Paginated } from "@/lib/types";

/** The last 10 workflow events across all documents; the full feed is on the History screen. */
export function RecentActivityCard() {
  const { data, error, loading } = useApiQuery<Paginated<ActivityEvent>>("/history/activity/?page_size=10");

  return (
    <section aria-label="فعالیت‌های اخیر" className="rounded-lg border border-slate-200 bg-white p-6">
      <div className="mb-4 flex items-baseline justify-between">
        <h2 className="text-lg font-semibold text-slate-900">فعالیت‌های اخیر</h2>
        <Link href="/documents/history" className="text-sm text-slate-600 underline">
          همهٔ سوابق
        </Link>
      </div>

      {loading && <p className="text-sm text-slate-500">در حال بارگذاری...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}
      {data && data.results.length === 0 && <p className="text-sm text-slate-500">هنوز فعالیتی ثبت نشده است.</p>}

      {data && data.results.length > 0 && (
        <ol className="space-y-3">
          {data.results.map((event) => (
            <li key={event.id} className="flex gap-3 text-sm">
              <span aria-hidden className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${EVENT_KIND_TONE[event.kind]}`} />
              <div className="min-w-0 flex-1">
                <p className="text-slate-900">
                  <span className="font-medium">{event.kind_label}</span>
                  <span className="text-slate-500"> — {event.actor_name}</span>
                </p>
                <p className="flex flex-wrap items-center gap-x-3 text-slate-600">
                  <Code>{event.document.full_code}</Code>
                  <Link href={`/documents/${event.document.id}/edit`} className="truncate hover:underline">
                    {event.document.title}
                  </Link>
                </p>
                {event.reason && <p className="mt-0.5 truncate text-slate-500" title={event.reason}>{event.reason}</p>}
              </div>
              <time className="shrink-0 text-xs text-slate-400" dateTime={event.created_at}>
                {formatJalaliDateTime(event.created_at)}
              </time>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
