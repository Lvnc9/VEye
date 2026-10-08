"use client";

import { useState } from "react";
import { useApiQuery } from "@/lib/use-api-query";
import { toPersianDigits } from "@/lib/jalali";
import Link from "next/link";
import { NC_SEVERITY_LABELS, RISK_LEVEL_LABELS, RISK_LEVEL_STYLE, type NcSeverity, type RiskLevel } from "@/lib/quality";
import {
  AGING_BUCKETS,
  KPI_DAYS_OPTIONS,
  agingWidth,
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
import { cx } from "@/components/ui/cx";
import { Activity, ClipboardCheck, Clock, FolderKanban, Gauge, ListChecks, RotateCcw, ShieldAlert, Users } from "lucide-react";

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
 * sends one back, where the projects stand, and (Phase 18) the quality figures. The document figures and
 * the quality figures marked «در این بازه» look back over a chosen window; the rest are about now and cover
 * only what the viewer may read.
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

      <Card aria-label="شاخص‌های کیفیت">
        <CardHeader title="کیفیت" icon={<ShieldAlert />} description={data?.quality.scope_note ?? "مواردی که شما حق دیدنشان را دارید"} />
        {!data ? (
          <SkeletonLines rows={4} />
        ) : (
          <QualityFigures quality={data.quality} days={days} />
        )}
      </Card>
    </div>
  );
}

/** The quality block: non-conformances (how many are open, how old, how fast they close), corrective
 *  actions (late now, on time in the window), audits and the risk register — each number with its words. */
function QualityFigures({ quality, days }: { quality: KpiResponse["quality"]; days: number }) {
  const { nonconformances: nc, actions, audits, risks } = quality;
  const span = `${toPersianDigits(days)} روز اخیر`;
  const severities = (Object.keys(NC_SEVERITY_LABELS) as NcSeverity[])
    .filter((key) => (nc.open_by_severity[key] ?? 0) > 0)
    .map((key) => `${toPersianDigits(nc.open_by_severity[key])} ${NC_SEVERITY_LABELS[key]}`);
  return (
    <>
      <dl className="grid gap-3 sm:grid-cols-3">
        <Stat
          label="عدم‌انطباق باز"
          value={toPersianDigits(nc.open)}
          note={`${toPersianDigits(nc.by_status.OPEN ?? 0)} منتظر بررسی · ${toPersianDigits(nc.by_status.IN_PROGRESS ?? 0)} در دست اقدام${severities.length ? ` · ${severities.join("، ")}` : ""} · ${toPersianDigits(nc.reported_in_window)} مورد تازه در ${span}`}
        />
        <Stat
          label="میانگین زمان تا بستن"
          value={formatDuration(nc.time_to_close.average_days)}
          note={
            nc.time_to_close.count === 0
              ? `از ثبت تا بستن — در ${span} موردی بسته نشده است.`
              : `از ثبت تا بستن · میانه ${formatDuration(nc.time_to_close.median_days)} · ${toPersianDigits(nc.time_to_close.count)} مورد بسته‌شده در ${span}`
          }
        />
        <Stat
          label="اقدام به‌موقع"
          value={formatPercent(actions.on_time_rate)}
          note={`${toPersianDigits(actions.on_time)} از ${toPersianDigits(actions.verified_in_window)} اقدام تاییدشده در ${span} پیش از مهلت انجام شده بود`}
        />
      </dl>

      <div className="mt-5 grid gap-6 lg:grid-cols-2">
        <section>
          <h3 className="mb-3 text-sm font-bold text-slate-800">سن عدم‌انطباق‌های باز</h3>
          {nc.open === 0 ? (
            <p className="text-xs text-slate-500">عدم‌انطباق بازی نیست.</p>
          ) : (
            <ul className="space-y-2">
              {AGING_BUCKETS.map(([key, label]) => (
                <li key={key} className="flex items-center gap-3 text-sm">
                  <span className="w-28 shrink-0 text-slate-700">{label}</span>
                  <ProgressBar value={agingWidth(nc.aging, key)} className="h-2 flex-1" />
                  <span className="w-10 shrink-0 text-end tabular-nums text-slate-700">{toPersianDigits(nc.aging[key])}</span>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-2 text-[11px] leading-5 text-slate-500">از زمان ثبت هر مورد تا امروز.</p>
        </section>

        <section>
          <h3 className="mb-3 flex items-center gap-2 text-sm font-bold text-slate-800">
            <Gauge className="size-4 text-brand-600" />
            ریسک‌های باز ({toPersianDigits(risks.live)})
          </h3>
          <ul className="flex flex-wrap gap-2">
            {(Object.keys(RISK_LEVEL_LABELS) as RiskLevel[]).map((level) => (
              <li key={level} className={cx("rounded-full px-3 py-1 text-xs font-bold ring-1 ring-inset", RISK_LEVEL_STYLE[level].chip)}>
                {RISK_LEVEL_LABELS[level]}: {toPersianDigits(risks.levels[level])}
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-slate-600">
            {toPersianDigits(risks.review_overdue)} ریسک از تاریخ بازنگری گذشته · {toPersianDigits(risks.without_owner)} ریسک بدون مسئول پیگیری
          </p>
        </section>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <p className="flex flex-wrap items-center gap-2 rounded-xl px-4 py-2.5 text-sm ring-1 ring-inset ring-slate-200">
          <ListChecks className="size-4 text-slate-400" />
          <span className="text-slate-600">اقدام‌های باز:</span>
          <b className="tabular-nums">{toPersianDigits(actions.open)}</b>
          {actions.overdue > 0 && <span className="text-xs font-bold text-rose-700">· {toPersianDigits(actions.overdue)} دیرکرد</span>}
        </p>
        <p className="flex flex-wrap items-center gap-2 rounded-xl px-4 py-2.5 text-sm ring-1 ring-inset ring-slate-200">
          <ClipboardCheck className="size-4 text-slate-400" />
          <span className="text-slate-600">ممیزی:</span>
          <span>
            {toPersianDigits(audits.completed_in_window)} انجام‌شده در {span} · {toPersianDigits(audits.in_progress)} در حال انجام ·{" "}
            {toPersianDigits(audits.planned)} برنامه‌ریزی‌شده
            {audits.late > 0 && <span className="font-bold text-rose-700"> ({toPersianDigits(audits.late)} از موعد گذشته)</span>} ·{" "}
            {toPersianDigits(audits.findings_in_window)} یافته
          </span>
        </p>
      </div>
      <p className="mt-3 text-[11px] leading-5 text-slate-500">
        «اقدام به‌موقع» یعنی کار پیش از مهلتش انجام و سپس تایید شده است. جزئیات در{" "}
        <Link href="/quality" className="underline hover:text-slate-800">عدم‌انطباق‌ها</Link>،{" "}
        <Link href="/quality/audits" className="underline hover:text-slate-800">ممیزی‌ها</Link> و{" "}
        <Link href="/quality/risks" className="underline hover:text-slate-800">ریسک‌ها</Link>.
      </p>
    </>
  );
}
