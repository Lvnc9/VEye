"use client";

import { useEffect, useState, type CSSProperties } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { FilePlus2, FileText, Hourglass, Inbox, PencilLine, PieChart, ShieldCheck, UserPlus, Users } from "lucide-react";
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
import { StatCard } from "@/components/ui/StatCard";
import { cx } from "@/components/ui/cx";
import type { DonutSlice } from "@/components/ui/DonutChart";

// The chart library only loads on pages that draw a chart, and never on the server.
const DonutChart = dynamic(() => import("@/components/ui/DonutChart"), {
  ssr: false,
  loading: () => <Skeleton className="mx-auto size-44 rounded-full" />,
});

/** Each document status in its badge's colour (StatusBadge: draft neutral, confirmation warning, approval
 *  brand, in force success, obsolete danger). */
const STATUS_COLOR: Record<DocumentStatus, string> = {
  DRAFT: "var(--color-slate-400)",
  AWAITING_CONFIRMATION: "var(--color-amber-500)",
  AWAITING_APPROVAL: "var(--color-sky-500)",
  UNDER_CONTROL: "var(--color-emerald-500)",
  OBSOLETE: "var(--color-rose-500)",
};

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
      <h3 className="mb-3 text-sm text-muted-foreground">{title}</h3>
      <ul className="space-y-3">
        {(Object.keys(labels) as K[]).map((key) => {
          const count = counts[key] ?? 0;
          const share = total > 0 ? count / total : 0;
          return (
            <li key={key} className="text-sm">
              <div className="mb-1 flex justify-between">
                <span className="text-soft-foreground">{labels[key]}</span>
                <span className="font-bold text-foreground tabular-nums">{count.toLocaleString("fa-IR")}</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                <div
                  className={cx("h-full w-full origin-right rounded-full transition-transform duration-1000 ease-out-quint", tone)}
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
  const share = (n: number) => (total ? n / total : 0);
  const underControl = metrics ? sumStatus(metrics, "UNDER_CONTROL") : null;
  const awaiting = metrics ? sumStatus(metrics, "AWAITING_CONFIRMATION", "AWAITING_APPROVAL") : null;
  const drafts = metrics ? sumStatus(metrics, "DRAFT") : null;
  const slices: DonutSlice[] = metrics
    ? metrics.statuses.map((status) => ({
        key: status.value,
        label: status.label,
        value: sumStatus(metrics, status.value),
        color: STATUS_COLOR[status.value] ?? "var(--color-slate-400)",
      }))
    : [];

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="veye-stagger" style={stagger(0)}>
          <p className="text-sm text-muted-foreground">
            {/* Client-only (the user arrives after hydration), so the server never renders a stale date. */}
            {user ? (
              <>
                {WEEKDAY.format(new Date())} {todayJalali()}
              </>
            ) : (
              " "
            )}
          </p>
          <h1 className="mt-1 text-2xl font-black leading-10 tracking-tight text-foreground sm:text-3xl sm:leading-[3rem]">
            {user ? (
              <>
                سلام،{" "}
                <span className="bg-gradient-to-l from-sky-600 to-indigo-600 bg-clip-text text-transparent dark:from-sky-300 dark:to-indigo-300">
                  {user.full_name}
                </span>
              </>
            ) : (
              "داشبورد مدیریت"
            )}
          </h1>
          <p className="mt-0.5 text-sm text-muted-foreground">نمای کلی مستندات، کارهای منتظر شما و آخرین فعالیت‌ها</p>
        </div>
        <div className="veye-stagger flex flex-wrap gap-2" style={stagger(1)}>
          <Link href="/inbox" className={buttonClass({ variant: "secondary" })}>
            <Inbox />
            کارتابل
          </Link>
          <Link href="/documents" className={buttonClass({ variant: "primary" })}>
            <FilePlus2 />
            ساخت مستند
          </Link>
        </div>
      </header>

      {error && <ErrorBanner message={error} />}

      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <StatCard index={1} label="کل مستندات" value={total} icon={<FileText />} tone="neutral" href="/documents" hint="در همهٔ گروه‌ها" />
        <StatCard
          index={2}
          label={metrics ? labelOf(metrics, "UNDER_CONTROL") : " "}
          value={underControl}
          icon={<ShieldCheck />}
          tone="success"
          share={underControl === null ? null : share(underControl)}
        />
        <StatCard
          index={3}
          label="در انتظار تایید و تصویب"
          value={awaiting}
          icon={<Hourglass />}
          tone="warning"
          share={awaiting === null ? null : share(awaiting)}
        />
        <StatCard
          index={4}
          label={metrics ? labelOf(metrics, "DRAFT") : " "}
          value={drafts}
          icon={<PencilLine />}
          tone="brand"
          share={drafts === null ? null : share(drafts)}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="veye-stagger space-y-6 xl:col-span-2" style={stagger(5)}>
          <AwaitingCard />
          <RecentActivityCard />
        </div>

        <div className="veye-stagger space-y-6" style={stagger(6)}>
          <Card aria-label="وضعیت مستندات" variant="gradient">
            <CardHeader title="وضعیت مستندات" icon={<PieChart />} description="سهم هر وضعیت از همهٔ مستندات" />
            {metrics ? (
              <DonutChart data={slices} totalLabel="مستند" />
            ) : (
              !error && <Skeleton className="mx-auto size-44 rounded-full" />
            )}
          </Card>

          <AnnouncementsCard />

          <Card aria-label="اطلاعات سامانه">
            <CardHeader
              title="اطلاعات سامانه"
              icon={<Users />}
              description={
                systemInfo ? (
                  <>
                    تعداد کل پرسنل:{" "}
                    <span className="font-bold text-foreground tabular-nums">{systemInfo.total.toLocaleString("fa-IR")}</span>
                  </>
                ) : undefined
              }
            />
            {systemInfo ? (
              <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-1">
                <Breakdown<AccessRoll>
                  title="به تفکیک نوع دسترسی"
                  labels={ACCESS_ROLL_LABELS}
                  counts={systemInfo.by_roll}
                  total={systemInfo.total}
                  tone="bg-gradient-to-l from-sky-400 to-sky-600"
                />
                <Breakdown<AccessLevel>
                  title="به تفکیک سطح"
                  labels={ACCESS_LEVEL_LABELS}
                  counts={systemInfo.by_level}
                  total={systemInfo.total}
                  tone="bg-gradient-to-l from-indigo-400 to-violet-600"
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
              <div className="mt-6 border-t border-border pt-5">
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
        <Card flush aria-label="کنترل مستندات" className="veye-stagger overflow-hidden" style={stagger(7)}>
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
                  <tr className="border-y border-border bg-muted/50 text-xs text-muted-foreground">
                    <th className="px-5 py-2.5 font-normal sm:px-6">نوع نامه</th>
                    {metrics.statuses.map((status) => (
                      <th key={status.value} className="whitespace-nowrap px-4 py-2.5 font-normal">
                        <span className="inline-flex items-center gap-1.5">
                          <span aria-hidden className="size-2 rounded-full" style={{ backgroundColor: STATUS_COLOR[status.value] }} />
                          {status.label}
                        </span>
                      </th>
                    ))}
                    <th className="px-5 py-2.5 font-normal sm:px-6">جمع</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {metrics.rows.map((row) => (
                    <tr key={row.group} className="transition-colors hover:bg-accent/60">
                      <td className="whitespace-nowrap px-5 py-3 font-bold text-foreground sm:px-6">{row.group}</td>
                      {metrics.statuses.map((status) => {
                        const count = row.counts[status.value] ?? 0;
                        return (
                          <td key={status.value} className={cx("px-4 py-3", count ? "text-foreground" : "text-subtle-foreground")}>
                            {count.toLocaleString("fa-IR")}
                          </td>
                        );
                      })}
                      <td className="px-5 py-3 font-bold text-foreground sm:px-6">{row.total.toLocaleString("fa-IR")}</td>
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
