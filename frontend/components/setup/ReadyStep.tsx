"use client";

import { useState } from "react";
import { ApiError, apiPost } from "@/lib/api-client";
import { countByKind, type OrgNode } from "@/lib/organization";
import { finishBlockedReason } from "@/lib/setup";
import type { SetupStatus } from "@/lib/types";
import { OrgTreeList } from "@/components/OrgTreeList";
import { DarkError, StepCard, ghostButton, primaryButton } from "./ui";
import { ArrowRight, Rocket } from "lucide-react";

/** Step 5: the finished chart and «ورود به نرم‌افزار». Finishing needs nothing structural — a company
 *  with only its root is a valid chart — but it does need a مدیر عامل: an active lead on the company
 *  root (ADR-010). Until then the button is disabled, says why, and points back to «پرسنل». */
export function ReadyStep({
  nodes,
  status,
  onBack,
  onPeople,
}: {
  nodes: OrgNode[];
  status: SetupStatus;
  onBack: () => void;
  onPeople: () => void;
}) {
  const counts = countByKind(nodes);
  const blocked = finishBlockedReason(status);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function finish() {
    setBusy(true);
    setError(null);
    try {
      await apiPost("/setup/complete/");
    } catch (err) {
      // "already completed" (another tab, another browser) is fine: the goal is reached. Any other
      // 409 (root_lead_missing — the lead was removed in another tab) is a real refusal.
      const code = err instanceof ApiError ? (err.data as { code?: string } | undefined)?.code : undefined;
      if (!(err instanceof ApiError && err.status === 409 && code === "already_completed")) {
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
          <div key={label} className="rounded-2xl border border-line bg-surface p-4 veye-rise" style={{ "--i": 0 } as React.CSSProperties}>
            <dd className="text-3xl font-bold text-accent tabular-nums">{count}</dd>
            <dt className="text-xs text-slate-400">{label}</dt>
          </div>
        ))}
      </dl>
      <div className="max-h-72 overflow-y-auto rounded-2xl border border-line bg-surface p-3">
        <OrgTreeList nodes={nodes} tone="dark" />
      </div>
      {blocked && (
        <div role="status" className="space-y-2 rounded-xl border border-amber-500/40 bg-amber-500/10 px-3.5 py-2.5 text-sm text-amber-200">
          <p>{blocked}</p>
          <button type="button" onClick={onPeople} className="underline hover:text-amber-100">
            رفتن به مرحلهٔ «پرسنل»
          </button>
        </div>
      )}
      {error && <DarkError message={error} />}
      <div className="flex justify-between">
        <button type="button" onClick={onBack} disabled={busy} className={ghostButton}>
          <ArrowRight className="size-4" />
          بازگشت
        </button>
        <button type="button" onClick={finish} disabled={busy || blocked !== null} className={primaryButton}>
          {busy ? "لحظه‌ای صبر کنید..." : "ورود به نرم‌افزار"}
          {!busy && <Rocket className="size-4" />}
        </button>
      </div>
    </StepCard>
  );
}
