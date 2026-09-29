"use client";

import { useState } from "react";
import Link from "next/link";
import { Building2, ShieldCheck, Sparkles, UserPlus } from "lucide-react";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
import { PersonnelForm } from "@/components/personnel/PersonnelForm";
import { UnassignedPeople } from "@/components/personnel/UnassignedPeople";
import { Avatar } from "@/components/ui/Avatar";
import { PageHeader } from "@/components/ui/PageHeader";
import { useCurrentUser } from "@/lib/current-user";
import type { OrgTreeResponse } from "@/lib/organization";
import { useApiQuery } from "@/lib/use-api-query";

/** The card beside the form: the profile as it will look, filled in while you type. */
function ProfilePreview({ draft }: { draft: { fullName: string; title: string; placement: string | null } }) {
  const empty = !draft.fullName && !draft.title && !draft.placement;
  return (
    <aside aria-label="پیش‌نمایش پروفایل" className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-card">
      {/* A navy header with the brand glow, like the sidebar the person will see. */}
      <div className="relative h-20 overflow-hidden bg-gradient-to-l from-surface to-surface-raised">
        <span aria-hidden className="absolute -top-10 left-1/2 size-40 -translate-x-1/2 rounded-full bg-accent/20 blur-2xl" />
      </div>
      <div className="-mt-9 px-5 pb-5 text-center">
        <span className="inline-flex rounded-full bg-white p-1 shadow-card">
          {draft.fullName ? (
            <Avatar key={draft.fullName.slice(0, 1)} name={draft.fullName} size="lg" className="size-16 text-lg animate-pop" />
          ) : (
            <span className="flex size-16 items-center justify-center rounded-full bg-slate-100 text-slate-300">
              <UserPlus className="size-7" />
            </span>
          )}
        </span>
        <p className="mt-3 truncate text-lg font-bold text-slate-900">{draft.fullName || "نام شخص"}</p>
        <p className="mt-0.5 flex min-h-6 items-center justify-center gap-1.5 text-sm text-slate-500">
          {draft.title ? (
            <>
              <ShieldCheck className="size-4 text-emerald-500" />
              {draft.title}
            </>
          ) : (
            "سمت پس از انتخاب دسترسی"
          )}
        </p>
        <div className="mt-4 rounded-xl bg-slate-50 px-3 py-2.5 text-sm ring-1 ring-inset ring-slate-200/70">
          <span className="flex items-center justify-center gap-1.5 text-slate-600">
            <Building2 className="size-4 text-brand-500" />
            {draft.placement ?? "هنوز جایی در ساختار ندارد"}
          </span>
        </div>
        {empty && (
          <p className="mt-4 flex items-center justify-center gap-1.5 text-xs text-slate-500">
            <Sparkles className="size-3.5 text-amber-500" />
            با پر کردن فرم، این کارت کامل می‌شود.
          </p>
        )}
      </div>
    </aside>
  );
}

/** Personnel Register page (skeleton.md §2/§3, cascaded placement in Phase 10 §B). */
export default function PersonnelRegisterPage() {
  const { can, loading: userLoading } = useCurrentUser();
  const [reload, setReload] = useState(0);
  const [draft, setDraft] = useState<{ fullName: string; title: string; placement: string | null }>({
    fullName: "",
    title: "",
    placement: null,
  });
  const tree = useApiQuery<OrgTreeResponse>("/org/tree/", reload);
  const nodes = tree.data?.nodes ?? [];

  if (userLoading) return <LoadingBanner />;
  if (!can("manage_personnel")) {
    return (
      <div className="mx-auto max-w-xl space-y-6">
        <PageHeader title="ساخت پروفایل پرسنل" />
        <ErrorBanner message="شما دسترسی لازم برای مدیریت پرسنل را ندارید." />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader
        title="ساخت پروفایل پرسنل"
        subtitle="شخص تازه‌ای را ثبت کنید و در همان‌جا در ساختار سازمان قرار دهید."
        actions={
          <Link
            href="/organization"
            className="inline-flex h-10 items-center gap-2 rounded-lg px-3 text-sm text-brand-700 transition-colors hover:bg-brand-50"
          >
            <Building2 className="size-4" />
            ساختار سازمان
          </Link>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
        <PersonnelForm
          tone="light"
          onDraft={setDraft}
          onRegistered={() => setReload((n) => n + 1)}
        />
        <div className="space-y-6 lg:sticky lg:top-4">
          <ProfilePreview draft={draft} />
        </div>
      </div>

      <UnassignedPeople nodes={nodes} reload={reload} onPlaced={() => setReload((n) => n + 1)} />
    </div>
  );
}
