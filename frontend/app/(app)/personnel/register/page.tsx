"use client";

import { useState } from "react";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
import { PersonnelForm } from "@/components/personnel/PersonnelForm";
import { UnassignedPeople } from "@/components/personnel/UnassignedPeople";
import { useCurrentUser } from "@/lib/current-user";
import type { OrgTreeResponse } from "@/lib/organization";
import { useApiQuery } from "@/lib/use-api-query";

/** Personnel Register page (skeleton.md §2/§3, cascaded placement in Phase 10 §B). */
export default function PersonnelRegisterPage() {
  const { can, loading: userLoading } = useCurrentUser();
  const [reload, setReload] = useState(0);
  const tree = useApiQuery<OrgTreeResponse>("/org/tree/", reload);
  const nodes = tree.data?.nodes ?? [];

  if (userLoading) return <LoadingBanner />;
  if (!can("manage_personnel")) {
    return (
      <div className="max-w-xl">
        <h1 className="mb-4 text-2xl font-bold text-slate-900">ساخت پروفایل پرسنل</h1>
        <ErrorBanner message="شما دسترسی لازم برای مدیریت پرسنل را ندارید." />
      </div>
    );
  }

  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">ساخت پروفایل پرسنل</h1>
      <PersonnelForm onRegistered={() => setReload((n) => n + 1)} tone="light" />
      <UnassignedPeople nodes={nodes} reload={reload} onPlaced={() => setReload((n) => n + 1)} />
    </div>
  );
}
