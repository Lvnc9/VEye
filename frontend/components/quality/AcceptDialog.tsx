"use client";

import { useState } from "react";
import { NC_SEVERITY_LABELS, type NcSeverity } from "@/lib/quality";
import { TextDialog } from "@/components/quality/TextDialog";
import { selectClass } from "@/components/ui/Field";

/**
 * Triage: «this is a real problem, here is why it happened». The root cause is required — a record
 * nobody has asked «why?» of is not ready for anyone to fix. The severity may be corrected on the way
 * (the reporter's first guess is rarely the last word).
 */
export function AcceptDialog({
  severity,
  onSubmit,
  onCancel,
}: {
  severity: NcSeverity;
  onSubmit: (rootCause: string, severity: NcSeverity) => Promise<void>;
  onCancel: () => void;
}) {
  const [chosen, setChosen] = useState<NcSeverity>(severity);
  return (
    <TextDialog
      title="پذیرش و ریشه‌یابی"
      description="این مورد را واقعی می‌دانید. ریشهٔ مشکل را بنویسید؛ پس از پذیرش می‌توانید اقدام اصلاحی تعیین کنید."
      fieldLabel="ریشهٔ مشکل"
      confirmLabel="پذیرش"
      extra={
        <label className="block text-sm">
          <span className="mb-1.5 block text-slate-700">شدت (در صورت نیاز اصلاح کنید)</span>
          <select value={chosen} onChange={(e) => setChosen(e.target.value as NcSeverity)} className={`${selectClass} w-full`}>
            {(Object.keys(NC_SEVERITY_LABELS) as NcSeverity[]).map((value) => (
              <option key={value} value={value}>
                {NC_SEVERITY_LABELS[value]}
              </option>
            ))}
          </select>
        </label>
      }
      onSubmit={(text) => onSubmit(text, chosen)}
      onCancel={onCancel}
    />
  );
}
