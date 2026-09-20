"use client";

import { useState } from "react";
import { ActivityTab } from "@/components/history/ActivityTab";
import { RevisionsTab } from "@/components/history/RevisionsTab";
import {
  EMPTY_ACTIVITY_FILTERS,
  EMPTY_REVISION_FILTERS,
  type ActivityFilters,
  type HistoryTab,
  type RevisionFilters,
} from "@/lib/history";

const TABS: { id: HistoryTab; label: string }[] = [
  { id: "revisions", label: "بازنگری‌ها" },
  { id: "activity", label: "فعالیت‌ها" },
];

/**
 * سوابق مستندات (Phase 6) — V_1.0's «Document History» button was dead, so this
 * is new. Filters live here (not in the tabs) so switching tabs keeps them.
 */
export default function DocumentHistoryPage() {
  const [tab, setTab] = useState<HistoryTab>("revisions");
  const [revisionFilters, setRevisionFilters] = useState<RevisionFilters>(EMPTY_REVISION_FILTERS);
  const [activityFilters, setActivityFilters] = useState<ActivityFilters>(EMPTY_ACTIVITY_FILTERS);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">سوابق مستندات</h1>
        <p className="mt-1 text-sm text-slate-500">بازنگری‌های همهٔ مستندات و تاریخچهٔ گردش کار آن‌ها</p>
      </header>

      <div role="tablist" aria-label="بخش‌های سوابق" className="flex gap-1 border-b border-slate-200">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            onClick={() => setTab(item.id)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
              tab === item.id
                ? "border-slate-900 text-slate-900"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === "revisions" ? (
        <RevisionsTab filters={revisionFilters} onFilters={setRevisionFilters} />
      ) : (
        <ActivityTab
          filters={activityFilters}
          onFilters={setActivityFilters}
          onOpenFamily={(family) => {
            setRevisionFilters({ ...EMPTY_REVISION_FILTERS, family });
            setTab("revisions");
          }}
        />
      )}
    </div>
  );
}
