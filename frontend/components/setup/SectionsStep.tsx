"use client";

import { chartLayout, type OrgNode } from "@/lib/organization";
import { AddNodeForm, DeleteNodeButton } from "./AddNodeForm";
import { StepCard, ghostButton, primaryButton } from "./ui";

/** Step 3: بخش‌ها. One card per active واحد, grouped under its حوزه (or «مستقیم زیر شرکت» for a
 *  واحد straight under the company). Each card has its own inline add form, so adding several
 *  بخش across several واحد never needs re-picking a shared selection. (بخش‌ها are where people and
 *  projects live, so they can also be added later from the chart.) */
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
  const layout = chartLayout(nodes);
  const floors = (layout?.floors ?? []).filter((floor) => floor.rooms.length > 0);

  return (
    <StepCard title="بخش‌ها" intro="بخش‌های هر واحد را همین‌جا بیفزایید. بخش‌ها همان‌جا هستند که افراد و پروژه‌ها جا می‌گیرند.">
      {floors.length === 0 ? (
        <p className="rounded-lg border border-dashed border-line p-4 text-sm text-slate-400">
          هنوز واحدی ندارید. به مرحلهٔ قبل برگردید و واحد بسازید، یا این مرحله را رد کنید.
        </p>
      ) : (
        <div className="space-y-6">
          {floors.map((floor) => (
            <div key={floor.node?.id ?? "loose"} className="space-y-3">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {floor.node ? floor.node.name : "مستقیم زیر شرکت"}
              </h3>
              <div className="space-y-4">
                {floor.rooms.map((room) => (
                  <div key={room.node.id} className="space-y-3 rounded-xl border border-line p-4">
                    <h4 className="text-sm font-semibold text-slate-100">{room.node.name}</h4>
                    <AddNodeForm
                      kind="SECTION"
                      parentId={room.node.id}
                      placeholder="نام بخش، مثلاً «بخش فروش داخلی»"
                      onChanged={onChanged}
                    />
                    {room.desks.length === 0 ? (
                      <p className="text-xs text-slate-500">این واحد هنوز بخشی ندارد.</p>
                    ) : (
                      <ul className="space-y-1">
                        {room.desks.map((section) => (
                          <li
                            key={section.id}
                            className="flex items-center justify-between rounded-lg bg-white/5 px-3 py-2 text-sm text-slate-200"
                          >
                            {section.name}
                            <DeleteNodeButton node={section} onChanged={onChanged} />
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
      <div className="flex justify-between">
        <button type="button" onClick={onBack} className={ghostButton}>
          بازگشت
        </button>
        <button type="button" onClick={onNext} className={primaryButton}>
          ادامه: پرسنل
        </button>
      </div>
    </StepCard>
  );
}
