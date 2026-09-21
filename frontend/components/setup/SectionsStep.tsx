"use client";

import { useState } from "react";
import { nodeOptions, pathLabel, type OrgNode } from "@/lib/organization";
import { AddNodeForm, DeleteNodeButton } from "./AddNodeForm";
import { StepCard, darkInput, ghostButton, primaryButton } from "./ui";

/** Step 3: بخش‌ها. Pick a واحد, add its بخش. (Sections are where people and projects live, so they
 *  can also be added later from the chart.) */
export function SectionsStep({
  nodes,
  onChanged,
  onBack,
  onNext,
}: {
  nodes: OrgNode[];
  onChanged: () => void;
  onBack: () => void;
  onNext: () => void;
}) {
  const units = nodeOptions(nodes, { kinds: ["UNIT"] });
  const [picked, setPicked] = useState<number | null>(null);
  const unitId = picked ?? units[0]?.id ?? null;
  const sections = nodes.filter((node) => node.kind === "SECTION" && node.parent === unitId);

  return (
    <StepCard title="بخش‌ها" intro="یک واحد را انتخاب کنید و بخش‌های آن را بیفزایید. بخش‌ها همان‌جا هستند که افراد و پروژه‌ها جا می‌گیرند.">
      {units.length === 0 ? (
        <p className="rounded-lg border border-dashed border-line p-4 text-sm text-slate-400">
          هنوز واحدی ندارید. به مرحلهٔ قبل برگردید و واحد بسازید، یا این مرحله را رد کنید.
        </p>
      ) : (
        <div className="space-y-4">
          <select
            aria-label="واحد"
            value={unitId ?? ""}
            onChange={(e) => setPicked(Number(e.target.value))}
            className={darkInput}
          >
            {units.map((option) => (
              <option key={option.id} value={option.id}>
                {pathLabel(nodes, option.id)}
              </option>
            ))}
          </select>
          {unitId !== null && (
            <>
              <AddNodeForm kind="SECTION" parentId={unitId} placeholder="نام بخش، مثلاً «بخش فروش داخلی»" onChanged={onChanged} />
              {sections.length === 0 ? (
                <p className="text-xs text-slate-500">این واحد هنوز بخشی ندارد.</p>
              ) : (
                <ul className="space-y-1">
                  {sections.map((section) => (
                    <li key={section.id} className="flex items-center justify-between rounded-lg bg-white/5 px-3 py-2 text-sm text-slate-200">
                      {section.name}
                      <DeleteNodeButton node={section} onChanged={onChanged} />
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
      )}
      <div className="flex justify-between">
        <button type="button" onClick={onBack} className={ghostButton}>
          بازگشت
        </button>
        <button type="button" onClick={onNext} className={primaryButton}>
          ادامه: آمادهٔ شروع
        </button>
      </div>
    </StepCard>
  );
}
