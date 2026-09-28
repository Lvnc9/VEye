"use client";

import Link from "next/link";
import { AwaitingCard } from "@/components/dashboard/AwaitingCard";
import type { InboxSummary } from "@/lib/chat";
import { formatJalali } from "@/lib/jalali";
import { AlarmClock, Target } from "lucide-react";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { SkeletonLines } from "@/components/ui/Skeleton";

/** «منتظر اقدام» (docs/11 §3.6): the documents waiting for my step — the dashboard's own card,
 *  reused so the two can never disagree — and my ریزهدف that are overdue or due soon. */
export function AwaitingTab({ summary }: { summary: InboxSummary | null }) {
  return (
    <div className="space-y-6">
      <AwaitingCard />
      <Card aria-label="ریزهدف‌های نزدیک به مهلت">
        <CardHeader
          title="ریزهدف‌های من"
          icon={<Target />}
          description="دیرکردها و آن‌هایی که تا چند روز آینده مهلت دارند"
        />
        {!summary ? (
          <SkeletonLines rows={3} />
        ) : summary.objectives.length === 0 ? (
          <EmptyState compact icon={<Target />} message="ریزهدفی نزدیک به مهلت ندارید." />
        ) : (
          <ul className="-mx-2 divide-y divide-slate-100">
            {summary.objectives.map((objective) => (
              <li key={objective.id} className="flex flex-wrap items-center gap-3 rounded-xl px-2 py-3 text-sm transition-colors hover:bg-slate-50">
                <Link href={`/projects/${objective.project.id}`} className="min-w-[10rem] flex-1 transition-colors hover:text-brand-700">
                  <span className="font-bold text-slate-900">{objective.title}</span>
                  <span className="text-slate-500"> — {objective.project.name}</span>
                </Link>
                <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-700 ring-1 ring-inset ring-slate-500/15">
                  {objective.status_label}
                </span>
                <span className={`inline-flex items-center gap-1 text-xs ${objective.is_overdue ? "font-bold text-rose-700" : "text-slate-500"}`}>
                  {objective.is_overdue && <AlarmClock className="size-3.5" />}
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
      </Card>
    </div>
  );
}
