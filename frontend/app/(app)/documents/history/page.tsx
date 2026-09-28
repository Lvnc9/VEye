"use client";

import { useState } from "react";
import { ActivityTab } from "@/components/history/ActivityTab";
import { RevisionsTab } from "@/components/history/RevisionsTab";
import { PageHeader } from "@/components/ui/PageHeader";
import { Tabs } from "@/components/ui/Tabs";
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
      <PageHeader title="سوابق مستندات" subtitle="بازنگری‌های همهٔ مستندات و تاریخچهٔ گردش کار آن‌ها" />

      <Tabs label="بخش‌های سوابق" items={TABS} value={tab} onChange={setTab} />

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
