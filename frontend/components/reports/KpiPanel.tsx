"use client";

import { useState } from "react";
import { useApiQuery } from "@/lib/use-api-query";
import { toPersianDigits } from "@/lib/jalali";
import {
  KPI_DAYS_OPTIONS,
  formatDuration,
  formatPercent,
  kpiPath,
  workloadWidth,
  type KpiResponse,
  type StepSummary,
} from "@/lib/reports";
import { ErrorBanner } from "@/components/StatusBanner";
import { Avatar } from "@/components/ui/Avatar";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { controlClass } from "@/components/ui/Field";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { SkeletonLines } from "@/components/ui/Skeleton";
import { Activity, Clock, FolderKanban, RotateCcw, Users } from "lucide-react";

/** One number with the words that say exactly what it measures — a KPI nobody can interpret is noise. */
function Stat({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="rounded-xl bg-slate-50 px-4 py-3 ring-1 ring-inset ring-slate-200/70">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="mt-1 text-2xl font-bold text-slate-900 tabular-nums">{value}</dd>
      <p className="mt-1 text-[11px] leading-5 text-slate-500">{note}</p>
    </div>
  );
}

function stepNote(step: StepSummary, what: string): string {
  if (step.count === 0) return `${what} — در این بازه موردی نبوده است.`;
  return `${what} · میانه ${formatDuration(step.median_days)} · طولانی‌ترین ${formatDuration(step.longest_days)} · ${toPersianDigits(step.count)} مورد`;
}

/**
 * «شاخص‌های کلیدی» (Phase 17): how long documents wait at each sign-off step, how often a reviewer
 * sends one back, and where the projects stand. The document figures look back over a chosen window;
 * the project figures are about now and cover only the projects the viewer may read.
 */
export function KpiPanel() {
  const [days, setDays] = useState<number>(90);
  const kpi = useApiQuery<KpiResponse>(kpiPath(days));

  if (kpi.error && !kpi.data) return <ErrorBanner message={kpi.error} />;
  const data = kpi.data;
  const busiest = Math.max(0, ...(data?.projects.workload.map((row) => row.open) ?? []));

  return (
    <div className="space-y-6">
      <Card aria-label="شاخص‌های مستندات">
        <CardHeader
          title="گردش مستندات"
          icon={<Clock />}
          description="از رویدادهای ثبت‌شدهٔ گردش‌کار محاسبه می‌شود — نه عددی ذخیره‌شده"
          actions={
            <select
              aria-label="بازهٔ زمانی"
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className={`${controlClass} h-9 px-2 text-sm`}
            >
              {KPI_DAYS_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {toPersianDigits(option)} روز اخیر
                </option>
              ))}
            </select>
          }
        />
        {!data ? (
          <SkeletonLines rows={4} />
        ) : (
          <>
            <dl className="grid gap-3 sm:grid-cols-3">
              <Stat
                label="میانگین زمان تا تایید"
                value={formatDuration(data.documents.confirm_step.average_days)}
                note={stepNote(data.documents.confirm_step, "از ارسال تا تایید")}
              />
              <Stat
                label="میانگین زمان تا تصویب"
                value={formatDuration(data.documents.approve_step.average_days)}
                note={stepNote(data.documents.approve_step, "از تایید تا تصویب")}
              />
              <Stat
                label="نرخ مرجوعی"
                value={formatPercent(data.documents.returns.rate)}
                note={`${toPersianDigits(data.documents.returns.returned)} مرجوع از ${toPersianDigits(data.documents.returns.decisions)} تصمیم (تایید، تصویب یا مرجوع)`}
              />
            </dl>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {(
                [
                  ["منتظر تایید", data.documents.waiting_now.confirmation],
                  ["منتظر تصویب", data.documents.waiting_now.approval],
                ] as const
              ).map(([label, waiting]) => (
                <p key={label} className="flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm ring-1 ring-inset ring-slate-200">
                  <RotateCcw className="size-4 text-slate-400" />
                  <span className="text-slate-600">{label} اکنون:</span>
                  <b className="tabular-nums">{toPersianDigits(waiting.count)}</b>
                  {waiting.oldest_days !== null && (
                    <span className="text-xs text-slate-500">· قدیمی‌ترین {formatDuration(waiting.oldest_days)}</span>
                  )}
                </p>
              ))}
            </div>
            <p className="mt-3 text-[11px] leading-5 text-slate-500">
              مرجوع‌شدن، شمارش زمان را از نو شروع می‌کند: مدتی که مستند پس از مرجوع در حالت پیش‌نویس بوده، جزو هیچ مرحله‌ای حساب نمی‌شود.
            </p>
          </>
        )}
      </Card>

      <Card aria-label="شاخص‌های پروژه‌ها">
        <CardHeader title="پروژه‌ها" icon={<FolderKanban />} description={data?.projects.scope_note ?? "پروژه‌هایی که شما حق دیدنشان را دارید"} />
        {!data ? (
          <SkeletonLines rows={4} />
        ) : data.projects.unfinished_count === 0 ? (
          <EmptyState compact icon={<Activity />} message="پروژهٔ در جریانی برای نمایش نیست." />
        ) : (
          <>
            <dl className="grid gap-3 sm:grid-cols-3">
              <Stat
                label="پیشرفت کلی"
                value={formatPercent(data.projects.progress)}
                note={`وزنی: ${toPersianDigits(data.projects.weight_done)} از ${toPersianDigits(data.projects.weight_total)} وزن ریزهدف‌ها در ${toPersianDigits(data.projects.unfinished_count)} پروژهٔ در جریان`}
              />
              <Stat
                label="ریزهدف دیرکرد"
                value={toPersianDigits(data.projects.overdue_objectives)}
                note={`در ${toPersianDigits(data.projects.projects_with_overdue)} پروژه`}
              />
              <Stat
                label="پروژه‌های در جریان"
                value={toPersianDigits(data.projects.unfinished_count)}
                note={`${toPersianDigits(data.projects.by_status.ACTIVE ?? 0)} در حال اجرا · ${toPersianDigits(data.projects.by_status.ON_HOLD ?? 0)} متوقف`}
              />
            </dl>
            <ProgressBar value={data.projects.progress} className="mt-4 h-2.5" label="پیشرفت کلی پروژه‌ها" />

            <h3 className="mt-6 mb-3 flex items-center gap-2 text-sm font-bold text-slate-800">
              <Users className="size-4 text-brand-600" />
              بار کاری — ریزهدف‌های باز هر نفر
            </h3>
            {data.projects.workload.length === 0 ? (
              <p className="text-xs text-slate-500">ریزهدف بازی به کسی واگذار نشده است.</p>
            ) : (
              <ul className="space-y-2">
                {data.projects.workload.map((row) => (
                  <li key={row.user} className="flex items-center gap-3 text-sm">
                    <Avatar name={row.name} size="sm" />
                    <span className="w-36 shrink-0 truncate text-slate-800">{row.name}</span>
                    <ProgressBar value={workloadWidth(row.open, busiest)} className="h-2 flex-1" />
                    <span className="w-24 shrink-0 text-end text-xs text-slate-600 tabular-nums">
                      {toPersianDigits(row.open)} باز
                      {row.overdue > 0 && <span className="text-rose-700"> · {toPersianDigits(row.overdue)} دیرکرد</span>}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
