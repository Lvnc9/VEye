"use client";

import Link from "next/link";
import { AwaitingCard } from "@/components/dashboard/AwaitingCard";
import type { InboxSummary } from "@/lib/chat";
import { formatJalali } from "@/lib/jalali";

/** «منتظر اقدام» (docs/11 §3.6): the documents waiting for my step — the dashboard's own card,
 *  reused so the two can never disagree — and my ریزهدف that are overdue or due soon. */
export function AwaitingTab({ summary }: { summary: InboxSummary | null }) {
  return (
    <div className="space-y-6">
      <AwaitingCard />
      <section aria-label="ریزهدف‌های نزدیک به مهلت" className="rounded-lg border border-slate-200 bg-white p-6">
        <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-lg font-semibold text-slate-900">ریزهدف‌های من</h2>
          <p className="text-xs text-slate-500">دیرکردها و آن‌هایی که تا چند روز آینده مهلت دارند</p>
        </div>
        {!summary ? (
          <p className="text-sm text-slate-500">در حال بارگذاری...</p>
        ) : summary.objectives.length === 0 ? (
          <p className="text-sm text-slate-500">ریزهدفی نزدیک به مهلت ندارید.</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {summary.objectives.map((objective) => (
              <li key={objective.id} className="flex flex-wrap items-center gap-3 py-2.5 text-sm">
                <Link href={`/projects/${objective.project.id}`} className="min-w-[10rem] flex-1 hover:underline">
                  <span className="font-medium text-slate-900">{objective.title}</span>
                  <span className="text-slate-500"> — {objective.project.name}</span>
                </Link>
                <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-700">{objective.status_label}</span>
                <span className={`text-xs ${objective.is_overdue ? "font-medium text-red-700" : "text-slate-500"}`}>
                  مهلت: {formatJalali(objective.due_on)}
                  {objective.is_overdue && " (دیرکرد)"}
                </span>
              </li>
            ))}
          </ul>
        )}
        {summary && summary.due_objectives > summary.objectives.length && (
          <p className="mt-3 text-xs text-slate-500">
            {summary.due_objectives - summary.objectives.length} مورد دیگر — در صفحهٔ هر پروژه ببینید.
          </p>
        )}
      </section>
    </div>
  );
}
