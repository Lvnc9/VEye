"use client";

import { nodeOptions, type OrgNode } from "@/lib/organization";
import type { AssignmentForm } from "@/lib/personnel-org";

const field = "w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm";

/** «جایگاه در ساختار سازمان» — an optional node, مسئول flag and position label, as part of the
 *  registration form. The chart has to be drawn first, so an empty chart says so instead. */
export function OrgPlacement({
  nodes,
  value,
  onChange,
}: {
  nodes: OrgNode[];
  value: AssignmentForm;
  onChange: (next: AssignmentForm) => void;
}) {
  const options = nodeOptions(nodes);
  if (options.length === 0) {
    return <p className="rounded border border-dashed border-slate-300 px-3 py-2 text-xs text-slate-500">ساختار سازمان هنوز تعریف نشده است؛ پس از ساختن آن می‌توانید افراد را جا بدهید.</p>;
  }

  return (
    <fieldset className="space-y-3 rounded-lg border border-slate-200 p-4">
      <legend className="px-2 text-sm font-medium text-slate-700">جایگاه در ساختار سازمان (اختیاری)</legend>
      <select
        aria-label="گره سازمانی"
        value={value.nodeId ?? ""}
        onChange={(e) => onChange({ ...value, nodeId: e.target.value ? Number(e.target.value) : null })}
        className={field}
      >
        <option value="">بدون جایگاه (بعداً)</option>
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.label} — {option.node.kind_label}
          </option>
        ))}
      </select>
      {value.nodeId !== null && (
        <>
          <input
            aria-label="عنوان در این گره"
            value={value.positionLabel}
            onChange={(e) => onChange({ ...value, positionLabel: e.target.value })}
            placeholder="عنوان در این گره، مثلاً «رئیس فروش» (اختیاری)"
            maxLength={255}
            className={field}
          />
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={value.isLead} onChange={(e) => onChange({ ...value, isLead: e.target.checked })} />
            مسئول این گره (می‌تواند ساختار و افراد آن را مدیریت کند)
          </label>
        </>
      )}
    </fieldset>
  );
}
