"use client";

import {
  ACCESS_LEVEL_LABELS,
  ACCESS_ROLL_LABELS,
  CAPABILITY_LABELS,
} from "@/lib/types";
import { formatJalali } from "@/lib/jalali";
import { useCurrentUser } from "@/lib/current-user";
import { LoadingBanner, ErrorBanner } from "@/components/StatusBanner";

export default function AccountPage() {
  const { user, loading } = useCurrentUser();

  if (loading) return <LoadingBanner label="در حال بارگذاری حساب..." />;
  if (!user) return <ErrorBanner message="پروفایل شما بارگذاری نشد." />;

  const rows: [string, string][] = [
    ["نام و نام خانوادگی", user.full_name],
    ["کد ملی", user.national_code],
    ["تلفن همراه", user.mobile_phone],
    ["نوع دسترسی", ACCESS_ROLL_LABELS[user.access_roll] ?? user.access_roll],
    ["سطح دسترسی", ACCESS_LEVEL_LABELS[user.access_level] ?? user.access_level],
    ["سمت", user.title],
    ["تاریخ عضویت", formatJalali(user.date_joined)],
  ];

  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">اکانت</h1>

      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
        <dl>
          {rows.map(([label, value], idx) => (
            <div
              key={label}
              className={`flex justify-between px-6 py-3 text-sm ${
                idx % 2 === 0 ? "bg-white" : "bg-slate-50"
              }`}
            >
              <dt className="font-medium text-slate-500">{label}</dt>
              <dd className="text-slate-900">{value}</dd>
            </div>
          ))}
        </dl>
      </div>

      <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold text-slate-900">دسترسی‌های شما</h2>
        {user.capabilities.length === 0 ? (
          <p className="text-sm text-slate-500">دسترسی خاصی تعریف نشده است.</p>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {user.capabilities.map((capability) => (
              <li
                key={capability}
                className="rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-700"
              >
                {CAPABILITY_LABELS[capability] ?? capability}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
