"use client";

import { ChevronLeft, Crown } from "lucide-react";
import { type OrgNode } from "@/lib/organization";
import { pickDomain, pickSection, pickUnit, placementOptions, resolvePlacement, type PlacementForm } from "@/lib/personnel-org";
import { cx } from "@/components/ui/cx";

const THEME = {
  light: {
    fieldset: "space-y-4 rounded-2xl border border-slate-200 bg-slate-50/50 p-4",
    legend: "px-2 text-sm font-bold text-slate-700",
    stepLabel: "text-slate-500",
    field:
      "h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-900 shadow-xs transition-[border-color,box-shadow] duration-150 " +
      "hover:border-slate-400 focus:border-brand-500 focus:outline-none focus:ring-4 focus:ring-brand-500/15",
    chevron: "text-slate-300",
    lead: "border-slate-200 bg-white text-slate-700 hover:border-slate-300 has-[:checked]:border-amber-300 has-[:checked]:bg-amber-50/70",
    leadText: "text-slate-500",
  },
  dark: {
    fieldset: "space-y-4 rounded-2xl border border-line bg-surface p-4",
    legend: "px-2 text-sm font-bold text-slate-300",
    stepLabel: "text-slate-400",
    field:
      "h-11 w-full rounded-xl border border-line bg-surface-raised px-3 text-sm text-slate-100 transition-[border-color,box-shadow] duration-150 " +
      "focus:border-accent focus:outline-none focus:ring-4 focus:ring-accent/20",
    chevron: "text-slate-600",
    lead: "border-line bg-surface-raised text-slate-200 hover:bg-white/5 has-[:checked]:border-amber-400/50 has-[:checked]:bg-amber-400/10",
    leadText: "text-slate-400",
  },
} as const;

const STEP_LABEL: Record<"domain" | "unit" | "section", string> = {
  domain: "حوزه",
  unit: "واحد",
  section: "بخش",
};

/**
 * «جایگاه در ساختار سازمان» — the حوزه → واحد → بخش cascade (ADR-010 §B), shared by
 * `PersonnelForm` (a brand-new person) and `UnassignedPeople` (an existing one). One request-worth
 * of options at a time; each answer only ever narrows the one below it, never itself. The steps sit
 * side by side (reading right to left) with a chevron between them; `bare` drops the frame and legend
 * when the caller already titles the section.
 */
export function PlacementCascade({
  nodes,
  value,
  onChange,
  tone = "light",
  bare = false,
}: {
  nodes: OrgNode[];
  value: PlacementForm;
  onChange: (next: PlacementForm) => void;
  tone?: "light" | "dark";
  bare?: boolean;
}) {
  const t = THEME[tone];
  const steps = placementOptions(nodes, value);
  const resolved = resolvePlacement(nodes, value);

  function apply(level: "domain" | "unit" | "section", raw: string) {
    if (level === "domain") onChange(pickDomain(value, raw));
    else if (level === "unit") onChange(pickUnit(value, raw));
    else onChange(pickSection(value, raw));
  }

  const body = (
    <>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        {steps.map((step, index) => (
          <div key={step.level} className="flex min-w-0 flex-1 items-end gap-2 animate-fade-in">
            {index > 0 && <ChevronLeft aria-hidden className={cx("mb-3.5 hidden size-4 shrink-0 sm:block", t.chevron)} />}
            <label className="block min-w-0 flex-1">
              <span className={cx("mb-1.5 block text-xs", t.stepLabel)}>{STEP_LABEL[step.level]}</span>
              <select
                aria-label={STEP_LABEL[step.level]}
                value={step.value}
                onChange={(e) => apply(step.level, e.target.value)}
                className={t.field}
              >
                <option value="">{`انتخاب ${STEP_LABEL[step.level]}…`}</option>
                {step.options.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        ))}
      </div>
      {resolved && (
        <div className="grid gap-3 animate-fade-in sm:grid-cols-2">
          <input
            aria-label="عنوان در این گره"
            value={value.positionLabel}
            onChange={(e) => onChange({ ...value, positionLabel: e.target.value })}
            placeholder="عنوان در این گره، مثلاً «رئیس فروش» (اختیاری)"
            maxLength={255}
            className={t.field}
          />
          <label
            className={cx(
              "flex min-h-11 cursor-pointer items-center gap-3 rounded-xl border px-3 py-2 text-sm transition-colors duration-150",
              t.lead,
            )}
          >
            <input
              type="checkbox"
              checked={value.isLead}
              onChange={(e) => onChange({ ...value, isLead: e.target.checked })}
              className="peer sr-only"
            />
            {/* A small switch: the knob slides when the person is made the node's lead. */}
            <span
              aria-hidden
              className="relative h-5 w-9 shrink-0 rounded-full bg-slate-300 transition-colors duration-200 peer-checked:bg-amber-500 peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-brand-500 after:absolute after:top-0.5 after:right-0.5 after:size-4 after:rounded-full after:bg-white after:shadow after:transition-transform after:duration-200 peer-checked:after:-translate-x-4"
            />
            <span className="min-w-0">
              <span className="flex items-center gap-1.5 font-bold">
                <Crown className="size-3.5 text-amber-500" />
                مسئول این گره
              </span>
              <span className={cx("block text-xs", t.leadText)}>می‌تواند ساختار و افراد آن را مدیریت کند</span>
            </span>
          </label>
        </div>
      )}
    </>
  );

  if (bare) return <div className="space-y-4">{body}</div>;
  return (
    <fieldset className={t.fieldset}>
      <legend className={t.legend}>جایگاه در ساختار سازمان (اختیاری)</legend>
      {body}
    </fieldset>
  );
}
