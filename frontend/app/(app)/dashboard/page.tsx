"use client";

import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import Link from "next/link";
import { FileText, Hourglass, PencilLine, ShieldCheck, UserPlus, Users } from "lucide-react";
import { apiGet, ApiError } from "@/lib/api-client";
import {
  ACCESS_LEVEL_LABELS,
  ACCESS_ROLL_LABELS,
  type AccessLevel,
  type AccessRoll,
  type DashboardMetrics,
  type DashboardSystemInfo,
  type DocumentStatus,
} from "@/lib/types";
import { ErrorBanner, EmptyBanner } from "@/components/StatusBanner";
import { useCurrentUser } from "@/lib/current-user";
import { todayJalali } from "@/lib/jalali";
import { AnnouncementsCard } from "@/components/dashboard/AnnouncementsCard";
import { AwaitingCard } from "@/components/dashboard/AwaitingCard";
import { RecentActivityCard } from "@/components/dashboard/RecentActivityCard";
import { Card, CardHeader } from "@/components/ui/Card";
import { buttonClass } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { cx } from "@/components/ui/cx";

const WEEKDAY = new Intl.DateTimeFormat("fa-IR", { weekday: "long" });

/** For a staggered entrance: the n-th card rises 40ms after the one before it. */
function stagger(i: number): CSSProperties {
  return { "--i": i } as CSSProperties;
}

function sumStatus(metrics: DashboardMetrics, ...statuses: DocumentStatus[]): number {
  return metrics.rows.reduce((total, row) => total + statuses.reduce((n, s) => n + (row.counts[s] ?? 0), 0), 0);
}

function labelOf(metrics: DashboardMetrics, status: DocumentStatus): string {
  return metrics.statuses.find((entry) => entry.value === status)?.label ?? status;
}

function StatTile({
  label,
  value,
  icon,
  tone,
  index,
}: {
  label: string;
  value: number | null;
  icon: ReactNode;
  tone: string;
  index: number;
}) {
  return (
    <div
      className="veye-stagger rounded-2xl border border-slate-200/80 bg-white p-4 shadow-card transition-[box-shadow,transform] duration-200 hover:-translate-y-0.5 hover:shadow-raised sm:p-5"
      style={stagger(index)}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-slate-500">{label}</p>
        <span className={cx("flex size-9 items-center justify-center rounded-xl [&_svg]:size-[18px]", tone)}>{icon}</span>
      </div>
      {value === null ? (
        <Skeleton className="mt-3 h-8 w-16" />
      ) : (
        <p className="mt-2 text-3xl font-bold leading-10 text-slate-900 tabular-nums">{value}</p>
      )}
    </div>
  );
}

/** One labelled bar per group: how the personnel split, at a glance. */
function Breakdown<K extends string>({
  title,
  labels,
  counts,
  total,
  tone,
}: {
  title: string;
  labels: Record<K, string>;
  counts: Partial<Record<K, number>>;
  total: number;
  tone: string;
}) {
  return (
    <div>
      <h3 className="mb-3 text-sm text-slate-500">{title}</h3>
      <ul className="space-y-3">
        {(Object.keys(labels) as K[]).map((key) => {
          const count = counts[key] ?? 0;
          const share = total > 0 ? count / total : 0;
          return (
            <li key={key} className="text-sm">
              <div className="mb-1 flex justify-between">
                <span className="text-slate-700">{labels[key]}</span>
                <span className="font-bold text-slate-900 tabular-nums">{count}</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
                <div
                  className={cx("h-full w-full origin-right rounded-full transition-transform duration-700 ease-out-quint", tone)}
                  style={{ transform: `scaleX(${share})` }}
                />
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default function DashboardPage() {
  const { user, can } = useCurrentUser();
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [systemInfo, setSystemInfo] = useState<DashboardSystemInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [m, s] = await Promise.all([
          apiGet<DashboardMetrics>("/dashboard/metrics/"),
          apiGet<DashboardSystemInfo>("/dashboard/system-info/"),
        ]);
        if (cancelled) return;
        setMetrics(m);
        setSystemInfo(s);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "دریافت اطلاعات داشبورد ممکن نشد.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const total = metrics ? metrics.rows.reduce((n, row) => n + row.total, 0) : null;

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold leading-10 text-slate-900">
            {user ? `سلام، ${user.full_name}` : "داشبورد مدیریت"}
          </h1>
          <p className="mt-0.5 text-sm text-slate-500">
            سامانه کنترل مستندات
            {/* Client-only (the user arrives after hydration), so the server never renders a stale date. */}
            {user && (
              <>
                {" · "}
                {WEEKDAY.format(new Date())} {todayJalali()}
              </>
            )}
          </p>
        </div>
      </header>

      {error && <ErrorBanner message={error} />}

      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <StatTile
          index={0}
          label="کل مستندات"
          value={total}
          icon={<FileText />}
          tone="bg-slate-100 text-slate-600"
        />
        <StatTile
          index={1}
          label={metrics ? labelOf(metrics, "UNDER_CONTROL") : " "}
          value={metrics ? sumStatus(metrics, "UNDER_CONTROL") : null}
          icon={<ShieldCheck />}
          tone="bg-emerald-50 text-emerald-600"
        />
        <StatTile
          index={2}
          label="در انتظار تایید و تصویب"
          value={metrics ? sumStatus(metrics, "AWAITING_CONFIRMATION", "AWAITING_APPROVAL") : null}
          icon={<Hourglass />}
          tone="bg-amber-50 text-amber-600"
        />
        <StatTile
          index={3}
          label={metrics ? labelOf(metrics, "DRAFT") : " "}
          value={metrics ? sumStatus(metrics, "DRAFT") : null}
          icon={<PencilLine />}
          tone="bg-brand-50 text-brand-700"
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-5">
        <div className="veye-stagger space-y-6 xl:col-span-3" style={stagger(4)}>
          <AwaitingCard />
          <RecentActivityCard />
        </div>

        <div className="veye-stagger space-y-6 xl:col-span-2" style={stagger(5)}>
          <AnnouncementsCard />
          <Card aria-label="اطلاعات سامانه">
            <CardHeader
              title="اطلاعات سامانه"
              icon={<Users />}
              description={
                systemInfo ? (
                  <>
                    تعداد کل پرسنل: <span className="font-bold text-slate-900 tabular-nums">{systemInfo.total}</span>
                  </>
                ) : undefined
              }
            />
            {systemInfo ? (
              <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
                <Breakdown<AccessRoll>
                  title="به تفکیک نوع دسترسی"
                  labels={ACCESS_ROLL_LABELS}
                  counts={systemInfo.by_roll}
                  total={systemInfo.total}
                  tone="bg-brand-500"
                />
                <Breakdown<AccessLevel>
                  title="به تفکیک سطح"
                  labels={ACCESS_LEVEL_LABELS}
                  counts={systemInfo.by_level}
                  total={systemInfo.total}
                  tone="bg-indigo-500"
                />
              </div>
            ) : (
              !error && (
                <div className="space-y-4">
                  <Skeleton className="h-3 w-1/3" />
                  <Skeleton className="h-2 w-full" />
                  <Skeleton className="h-2 w-10/12" />
                  <Skeleton className="h-2 w-9/12" />
                </div>
              )
            )}
            {systemInfo && can("manage_personnel") && (
              <div className="mt-6 border-t border-slate-100 pt-5">
                <Link href="/personnel/register" className={buttonClass({ variant: "subtle" })}>
                  <UserPlus />
                  ساخت پروفایل پرسنل
                </Link>
              </div>
            )}
          </Card>
        </div>
      </div>

      {metrics && (
        <Card flush aria-label="کنترل مستندات" className="veye-stagger overflow-hidden" style={stagger(6)}>
          <div className="px-5 pt-5 sm:px-6 sm:pt-6">
            <CardHeader title="کنترل مستندات" icon={<FileText />} description="تعداد مستندات هر گروه در هر وضعیت" />
          </div>
          {metrics.rows.every((row) => row.total === 0) ? (
            <div className="px-5 pb-6 sm:px-6">
              <EmptyBanner message="هنوز مستندی ثبت نشده است." />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-right text-sm tabular-nums">
                <thead>
                  <tr className="border-y border-slate-100 bg-slate-50/80 text-xs text-slate-500">
                    <th className="px-5 py-2.5 font-normal sm:px-6">نوع نامه</th>
                    {metrics.statuses.map((status) => (
                      <th key={status.value} className="whitespace-nowrap px-4 py-2.5 font-normal">
                        {status.label}
                      </th>
                    ))}
                    <th className="px-5 py-2.5 font-normal sm:px-6">جمع</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {metrics.rows.map((row) => (
                    <tr key={row.group} className="transition-colors hover:bg-slate-50/70">
                      <td className="whitespace-nowrap px-5 py-3 font-bold text-slate-800 sm:px-6">{row.group}</td>
                      {metrics.statuses.map((status) => {
                        const count = row.counts[status.value] ?? 0;
                        return (
                          <td key={status.value} className={cx("px-4 py-3", count ? "text-slate-800" : "text-slate-300")}>
                            {count}
                          </td>
                        );
                      })}
                      <td className="px-5 py-3 font-bold text-slate-900 sm:px-6">{row.total}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
