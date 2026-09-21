"use client";

import { useState } from "react";
import { ApiError, apiPost } from "@/lib/api-client";
import { countByKind, type OrgNode } from "@/lib/organization";
import { OrgTreeList } from "@/components/OrgTreeList";
import { DarkError, StepCard, ghostButton, primaryButton } from "./ui";

/** Step 4: the finished chart and «ورود به نرم‌افزار». Finishing needs nothing structural — a company
 *  with only its root is a valid chart, and the manager can keep drawing it from the app. */
export function ReadyStep({ nodes, onBack }: { nodes: OrgNode[]; onBack: () => void }) {
  const counts = countByKind(nodes);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function finish() {
    setBusy(true);
    setError(null);
    try {
      await apiPost("/setup/complete/");
    } catch (err) {
      // "already completed" (another tab, another browser) is fine: the goal is reached.
      if (!(err instanceof ApiError && err.status === 409)) {
        setError(err instanceof ApiError ? err.message : "پایان راه‌اندازی ممکن نشد.");
        setBusy(false);
        return;
      }
    }
    // Deliberate full-page navigation: leave the wizard with fresh client state (sidebar, company name).
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.href = "/dashboard";
  }

  return (
    <StepCard title="آمادهٔ شروع" intro="ساختار سازمان شما ساخته شد. می‌توانید آن را همیشه از بخش «ساختار سازمان» در نرم‌افزار ادامه دهید.">
      <dl className="grid grid-cols-3 gap-3 text-center">
        {[
          ["حوزه", counts.DOMAIN],
          ["واحد", counts.UNIT],
          ["بخش", counts.SECTION],
        ].map(([label, count]) => (
          <div key={label} className="rounded-xl border border-line p-3">
            <dd className="text-2xl font-bold text-accent">{count}</dd>
            <dt className="text-xs text-slate-400">{label}</dt>
          </div>
        ))}
      </dl>
      <div className="max-h-72 overflow-y-auto rounded-xl border border-line p-3">
        <OrgTreeList nodes={nodes} tone="dark" />
      </div>
      {error && <DarkError message={error} />}
      <div className="flex justify-between">
        <button type="button" onClick={onBack} disabled={busy} className={ghostButton}>
          بازگشت
        </button>
        <button type="button" onClick={finish} disabled={busy} className={primaryButton}>
          {busy ? "لحظه‌ای صبر کنید..." : "ورود به نرم‌افزار"}
        </button>
      </div>
    </StepCard>
  );
}
