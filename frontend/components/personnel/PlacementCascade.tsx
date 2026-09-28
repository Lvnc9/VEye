"use client";

import { darkInput } from "@/components/setup/ui";
import { type OrgNode } from "@/lib/organization";
import { pickDomain, pickSection, pickUnit, placementOptions, resolvePlacement, type PlacementForm } from "@/lib/personnel-org";
import { controlClass } from "@/components/ui/Field";

const LIGHT = {
  fieldset: "space-y-3 rounded-lg border border-slate-200 p-4",
  legend: "px-2 text-sm font-medium text-slate-700",
  field: `${controlClass} w-full px-3 py-2 text-sm`,
  checkboxLabel: "flex items-center gap-2 text-sm text-slate-700",
};

const DARK = {
  fieldset: "space-y-3 rounded-lg border border-line bg-surface p-4",
  legend: "px-2 text-sm font-medium text-slate-300",
  field: darkInput,
  checkboxLabel: "flex items-center gap-2 text-sm text-slate-300",
};

const STEP_LABEL: Record<"domain" | "unit" | "section", string> = {
  domain: "حوزه",
  unit: "واحد",
  section: "بخش",
};

/**
 * «جایگاه در ساختار سازمان» — the حوزه → واحد → بخش cascade (ADR-010 §B), shared by
 * `PersonnelForm` (a brand-new person) and `UnassignedPeople` (an existing one). One request-worth
 * of options at a time; each answer only ever narrows the one below it, never itself.
 */
export function PlacementCascade({
  nodes,
  value,
  onChange,
  tone = "light",
}: {
  nodes: OrgNode[];
  value: PlacementForm;
  onChange: (next: PlacementForm) => void;
  tone?: "light" | "dark";
}) {
  const t = tone === "dark" ? DARK : LIGHT;
  const steps = placementOptions(nodes, value);
  const resolved = resolvePlacement(nodes, value);

  function apply(level: "domain" | "unit" | "section", raw: string) {
    if (level === "domain") onChange(pickDomain(value, raw));
    else if (level === "unit") onChange(pickUnit(value, raw));
    else onChange(pickSection(value, raw));
  }

  return (
    <fieldset className={t.fieldset}>
      <legend className={t.legend}>جایگاه در ساختار سازمان (اختیاری)</legend>
      {steps.map((step) => (
        <select
          key={step.level}
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
      ))}
      {resolved && (
        <>
          <input
            aria-label="عنوان در این گره"
            value={value.positionLabel}
            onChange={(e) => onChange({ ...value, positionLabel: e.target.value })}
            placeholder="عنوان در این گره، مثلاً «رئیس فروش» (اختیاری)"
            maxLength={255}
            className={t.field}
          />
          <label className={t.checkboxLabel}>
            <input
              type="checkbox"
              checked={value.isLead}
              onChange={(e) => onChange({ ...value, isLead: e.target.checked })}
            />
            مسئول این گره (می‌تواند ساختار و افراد آن را مدیریت کند)
          </label>
        </>
      )}
    </fieldset>
  );
}
