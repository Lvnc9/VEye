"use client";

import type { OrgNode } from "@/lib/organization";
import { AddNodeForm, DeleteNodeButton } from "./AddNodeForm";
import { StepCard, ghostButton, primaryButton } from "./ui";

/** Step 2: واحدها. Each حوزه gets its own list and form; a company with no حوزه gets one for the
 *  company itself — the واحد then hang straight under it. */
export function UnitsStep({
  rootId,
  rootName,
  nodes,
  onChanged,
  onBack,
  onNext,
}: {
  rootId: number;
  rootName: string;
  nodes: OrgNode[];
  onChanged: () => void;
  onBack: () => void;
  onNext: () => void;
}) {
  const domains = nodes.filter((node) => node.kind === "DOMAIN" && node.is_active);
  const parents = domains.length > 0 ? domains : [{ id: rootId, name: rootName }];

  return (
    <StepCard title="واحدها" intro="در هر حوزه، واحدهای آن را بیفزایید. اگر شرکت حوزه ندارد، واحدها مستقیم زیر شرکت ساخته می‌شوند.">
      <div className="space-y-6">
        {parents.map((parent) => {
          const units = nodes.filter((node) => node.kind === "UNIT" && node.parent === parent.id);
          return (
            <div key={parent.id} className="space-y-3 rounded-xl border border-line p-4">
              <h3 className="text-sm font-semibold text-slate-100">{parent.name}</h3>
              <AddNodeForm kind="UNIT" parentId={parent.id} placeholder="نام واحد، مثلاً «واحد فروش»" onChanged={onChanged} />
              {units.length === 0 ? (
                <p className="text-xs text-slate-500">هنوز واحدی نیفزوده‌اید.</p>
              ) : (
                <ul className="space-y-1">
                  {units.map((unit) => (
                    <li key={unit.id} className="flex items-center justify-between rounded-lg bg-white/5 px-3 py-2 text-sm text-slate-200">
                      {unit.name}
                      <DeleteNodeButton node={unit} onChanged={onChanged} />
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>
      <div className="flex justify-between">
        <button type="button" onClick={onBack} className={ghostButton}>
          بازگشت
        </button>
        <button type="button" onClick={onNext} className={primaryButton}>
          ادامه: بخش‌ها
        </button>
      </div>
    </StepCard>
  );
}
