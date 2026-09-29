"use client";

import type { ComponentType } from "react";
import { BadgeCheck, Building2, CalendarDays, Crown, IdCard, KeyRound, Layers, Phone, ShieldCheck, UserRound } from "lucide-react";
import { ACCESS_LEVEL_LABELS, ACCESS_ROLL_LABELS, CAPABILITY_LABELS } from "@/lib/types";
import { ORG_KIND_LABELS } from "@/lib/organization";
import { formatJalali } from "@/lib/jalali";
import { useCurrentUser } from "@/lib/current-user";
import { LoadingBanner, ErrorBanner } from "@/components/StatusBanner";
import { Avatar } from "@/components/ui/Avatar";
import { Card, CardHeader, cardClass } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { cx } from "@/components/ui/cx";

export default function AccountPage() {
  const { user, loading } = useCurrentUser();

  if (loading) return <LoadingBanner label="در حال بارگذاری حساب..." />;
  if (!user) return <ErrorBanner message="پروفایل شما بارگذاری نشد." />;

  const rows: { label: string; value: string; icon: ComponentType<{ className?: string }>; latin?: boolean }[] = [
    { label: "نام و نام خانوادگی", value: user.full_name, icon: UserRound },
    { label: "کد ملی", value: user.national_code, icon: IdCard, latin: true },
    { label: "تلفن همراه", value: user.mobile_phone || "—", icon: Phone, latin: true },
    { label: "نوع دسترسی", value: ACCESS_ROLL_LABELS[user.access_roll] ?? user.access_roll, icon: KeyRound },
    { label: "سطح دسترسی", value: ACCESS_LEVEL_LABELS[user.access_level] ?? user.access_level, icon: Layers },
    { label: "سمت", value: user.title, icon: BadgeCheck },
    { label: "تاریخ عضویت", value: formatJalali(user.date_joined), icon: CalendarDays },
  ];
  const memberships = user.memberships ?? [];

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      {/* The profile banner: navy with the brand glow, the avatar overlapping its edge. */}
      <section className={cx(cardClass, "overflow-hidden")}>
        <div className="relative h-28 overflow-hidden bg-gradient-to-l from-surface to-surface-raised">
          <span aria-hidden className="absolute -top-16 left-1/4 size-56 rounded-full bg-accent/20 blur-3xl" />
          <span
            aria-hidden
            className="absolute inset-0 bg-[radial-gradient(circle_at_1px_1px,rgb(148_163_184/0.15)_1px,transparent_0)] bg-[length:20px_20px]"
          />
        </div>
        <div className="flex flex-wrap items-end gap-4 px-5 pb-5 sm:px-6">
          <span className="-mt-10 inline-flex rounded-full bg-white p-1.5 shadow-card">
            <Avatar name={user.full_name} size="lg" className="size-20 text-xl" />
          </span>
          <div className="min-w-0 flex-1 pt-3">
            <h1 className="truncate text-2xl font-bold leading-10 text-slate-900">{user.full_name}</h1>
            <p className="flex items-center gap-1.5 text-sm text-slate-500">
              <ShieldCheck className="size-4 text-emerald-500" />
              {user.title}
              {user.company && (
                <>
                  <span className="text-slate-300">·</span>
                  {user.company.name}
                </>
              )}
            </p>
          </div>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Card flush className="overflow-hidden" aria-label="مشخصات">
          <div className="px-5 pt-5 sm:px-6">
            <CardHeader title="مشخصات" icon={<UserRound />} />
          </div>
          <dl className="divide-y divide-slate-100 border-t border-slate-100">
            {rows.map(({ label, value, icon: Icon, latin }) => (
              <div key={label} className="flex items-center justify-between gap-4 px-5 py-3 text-sm sm:px-6">
                <dt className="flex items-center gap-2 text-slate-500">
                  <Icon className="size-4 text-slate-400" />
                  {label}
                </dt>
                <dd className={cx("text-end font-bold text-slate-900", latin && "latn")}>{value}</dd>
              </div>
            ))}
          </dl>
        </Card>

        <div className="space-y-6">
          <Card aria-label="جایگاه در سازمان">
            <CardHeader title="جایگاه در سازمان" icon={<Building2 />} />
            {memberships.length === 0 ? (
              <EmptyState compact icon={<Building2 />} message="هنوز در ساختار سازمان جایی ندارید." />
            ) : (
              <ul className="space-y-2">
                {memberships.map((membership) => (
                  <li
                    key={membership.id}
                    className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 px-3 py-2.5 text-sm"
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">
                        {ORG_KIND_LABELS[membership.node_kind]}
                      </span>
                      <span className="truncate font-bold text-slate-900">{membership.node_name}</span>
                    </span>
                    {membership.is_lead && (
                      <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-xs text-amber-800 ring-1 ring-inset ring-amber-600/25">
                        <Crown className="size-3.5" />
                        مسئول
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card aria-label="دسترسی‌های شما">
            <CardHeader
              title="دسترسی‌های شما"
              icon={<KeyRound />}
              actions={
                user.capabilities.length > 0 && (
                  <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-600 tabular-nums">
                    {user.capabilities.length.toLocaleString("fa-IR")}
                  </span>
                )
              }
            />
            {user.capabilities.length === 0 ? (
              <EmptyState compact icon={<KeyRound />} message="دسترسی خاصی تعریف نشده است." />
            ) : (
              <ul className="grid gap-2 sm:grid-cols-2">
                {user.capabilities.map((capability, i) => (
                  <li
                    key={capability}
                    className="veye-stagger flex items-center gap-2 rounded-xl bg-brand-50/70 px-3 py-2 text-sm text-brand-900 ring-1 ring-inset ring-brand-600/10"
                    style={{ "--i": i } as React.CSSProperties}
                  >
                    <BadgeCheck className="size-4 text-brand-600" />
                    {CAPABILITY_LABELS[capability] ?? capability}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
