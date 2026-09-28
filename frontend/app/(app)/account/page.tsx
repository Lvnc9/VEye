"use client";

import {
  ACCESS_LEVEL_LABELS,
  ACCESS_ROLL_LABELS,
  CAPABILITY_LABELS,
} from "@/lib/types";
import { formatJalali } from "@/lib/jalali";
import { useCurrentUser } from "@/lib/current-user";
import { LoadingBanner, ErrorBanner } from "@/components/StatusBanner";
import { Avatar } from "@/components/ui/Avatar";

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
    <div className="mx-auto max-w-xl space-y-6">
      <h1 className="text-2xl font-bold leading-10 text-slate-900">اکانت</h1>

      <div className="flex items-center gap-4 rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card">
        <Avatar name={user.full_name} size="lg" className="size-14 text-base" />
        <div className="min-w-0">
          <p className="truncate text-lg font-bold text-slate-900">{user.full_name}</p>
          <p className="truncate text-sm text-slate-500">{user.title}</p>
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-card">
        <dl>
          {rows.map(([label, value], idx) => (
            <div
              key={label}
              className={`flex justify-between gap-4 px-5 py-3 text-sm sm:px-6 ${idx > 0 ? "border-t border-slate-100" : ""}`}
            >
              <dt className="text-slate-500">{label}</dt>
              <dd className="text-end font-bold text-slate-900">{value}</dd>
            </div>
          ))}
        </dl>
      </div>

      <section className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card sm:p-6">
        <h2 className="mb-3 text-lg font-bold text-slate-900">دسترسی‌های شما</h2>
        {user.capabilities.length === 0 ? (
          <p className="text-sm text-slate-500">دسترسی خاصی تعریف نشده است.</p>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {user.capabilities.map((capability) => (
              <li
                key={capability}
                className="rounded-full bg-brand-50 px-3 py-1 text-sm text-brand-800 ring-1 ring-inset ring-brand-600/15"
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
