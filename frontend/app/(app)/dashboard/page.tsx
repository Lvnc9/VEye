"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiGet, ApiError } from "@/lib/api-client";
import {
  ACCESS_LEVEL_LABELS,
  ACCESS_ROLL_LABELS,
  type AccessLevel,
  type AccessRoll,
  type DashboardMetrics,
  type DashboardSystemInfo,
} from "@/lib/types";
import { LoadingBanner, ErrorBanner, EmptyBanner } from "@/components/StatusBanner";
import { useCurrentUser } from "@/lib/current-user";
import { AwaitingCard } from "@/components/dashboard/AwaitingCard";
import { RecentActivityCard } from "@/components/dashboard/RecentActivityCard";

export default function DashboardPage() {
  const { can } = useCurrentUser();
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [systemInfo, setSystemInfo] = useState<DashboardSystemInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

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
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">داشبورد مدیریت</h1>
        <p className="mt-1 text-sm text-slate-500">سامانه کنترل مستندات</p>
      </header>

      <AwaitingCard />

      {loading && <LoadingBanner />}
      {error && <ErrorBanner message={error} />}

      {systemInfo && (
        <section className="rounded-lg border border-slate-200 bg-white p-6">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">اطلاعات سامانه</h2>
          <p className="mb-4 text-sm text-slate-600">
            تعداد کل پرسنل: <span className="font-semibold">{systemInfo.total}</span>
          </p>
          <div className="grid gap-6 sm:grid-cols-2">
            <div>
              <h3 className="mb-2 text-sm font-medium text-slate-700">به تفکیک نوع دسترسی</h3>
              <ul className="space-y-1 text-sm text-slate-600">
                {(Object.keys(ACCESS_ROLL_LABELS) as AccessRoll[]).map((roll) => (
                  <li key={roll} className="flex justify-between">
                    <span>{ACCESS_ROLL_LABELS[roll]}</span>
                    <span>{systemInfo.by_roll[roll] ?? 0}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="mb-2 text-sm font-medium text-slate-700">به تفکیک سطح</h3>
              <ul className="space-y-1 text-sm text-slate-600">
                {(Object.keys(ACCESS_LEVEL_LABELS) as AccessLevel[]).map((level) => (
                  <li key={level} className="flex justify-between">
                    <span>{ACCESS_LEVEL_LABELS[level]}</span>
                    <span>{systemInfo.by_level[level] ?? 0}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          {can("manage_personnel") && (
            <div className="mt-6">
              <Link
                href="/personnel/register"
                className="inline-block rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700"
              >
                ساخت پروفایل پرسنل
              </Link>
            </div>
          )}
        </section>
      )}

      <RecentActivityCard />

      {metrics && (
        <section className="rounded-lg border border-slate-200 bg-white p-6">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">کنترل مستندات</h2>
          {metrics.rows.every((row) => row.total === 0) ? (
            <EmptyBanner message="هنوز مستندی ثبت نشده است." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-right text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-600">
                    <th className="py-2 pl-4 font-medium">نوع نامه</th>
                    {metrics.statuses.map((status) => (
                      <th key={status.value} className="py-2 pl-4 font-medium">
                        {status.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {metrics.rows.map((row) => (
                    <tr key={row.group} className="border-b border-slate-100">
                      <td className="py-2 pl-4 font-medium text-slate-800">{row.group}</td>
                      {metrics.statuses.map((status) => (
                        <td key={status.value} className="py-2 pl-4 text-slate-600">
                          {row.counts[status.value] ?? 0}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
