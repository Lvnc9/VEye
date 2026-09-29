"use client";

import { useState } from "react";
import { OrgTreeList } from "@/components/OrgTreeList";
import { OrgChart } from "@/components/org/OrgChart";
import { NodePanel } from "@/components/org/NodePanel";
import { EmptyBanner, ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
import { useApiQuery } from "@/lib/use-api-query";
import { countByKind, type Company, type OrgNode, type OrgTreeResponse } from "@/lib/organization";
import { MousePointerClick } from "lucide-react";
import { EmptyState } from "@/components/ui/EmptyState";

/** «ساختار سازمان»: the company as a building (graphic view) or as a plain tree (compact view). */
export default function OrganizationPage() {
  const [reload, setReload] = useState(0);
  const tree = useApiQuery<OrgTreeResponse>("/org/tree/", reload);
  const company = useApiQuery<Company>("/org/company/", reload);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [compact, setCompact] = useState(false);
  const [showArchived, setShowArchived] = useState(false);

  if (tree.loading || company.loading) return <LoadingBanner />;
  // 404 before setup: the manager is pointed to the wizard by the banner in the app shell.
  if (company.error && !company.data) return <EmptyBanner message="شرکت هنوز راه‌اندازی نشده است." />;
  if (tree.error || !tree.data) return <ErrorBanner message={tree.error ?? "دریافت ساختار سازمان ممکن نشد."} />;

  const nodes = tree.data.nodes;
  const selected = nodes.find((node) => node.id === selectedId) ?? null;
  const counts = countByKind(nodes);

  function structureChanged(next?: { selectId?: number | null }) {
    setReload((n) => n + 1);
    if (next && "selectId" in next) setSelectedId(next.selectId ?? null);
  }

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold leading-10 text-slate-900">{company.data?.name ?? "ساختار سازمان"}</h1>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm">
            {(
              [
                ["DOMAIN", "حوزه", "bg-indigo-50 text-indigo-800 ring-indigo-600/20"],
                ["UNIT", "واحد", "bg-brand-50 text-brand-800 ring-brand-600/20"],
                ["SECTION", "بخش", "bg-emerald-50 text-emerald-800 ring-emerald-600/20"],
              ] as const
            ).map(([kind, label, tone]) => (
              <span key={kind} className={`rounded-full px-2.5 py-0.5 text-xs ring-1 ring-inset tabular-nums ${tone}`}>
                {counts[kind]} {label}
              </span>
            ))}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm text-slate-700">
          <label className="flex h-9 items-center gap-2 rounded-lg px-3 ring-1 ring-inset ring-slate-200 transition-colors hover:bg-slate-50 has-[:checked]:bg-brand-50 has-[:checked]:text-brand-800 has-[:checked]:ring-brand-300">
            <input type="checkbox" className="size-4 rounded" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
            نمایش بایگانی‌شده‌ها
          </label>
          <label className="flex h-9 items-center gap-2 rounded-lg px-3 ring-1 ring-inset ring-slate-200 transition-colors hover:bg-slate-50 has-[:checked]:bg-brand-50 has-[:checked]:text-brand-800 has-[:checked]:ring-brand-300">
            <input type="checkbox" className="size-4 rounded" checked={compact} onChange={(e) => setCompact(e.target.checked)} />
            نمای فشرده
          </label>
        </div>
      </header>

      {tree.data.truncated && (
        <p className="rounded-xl border border-amber-200 bg-amber-50/80 px-3 py-2 text-sm text-amber-800">
          ساختار بسیار بزرگ است و فقط دو سطح بالا نمایش داده می‌شود.
        </p>
      )}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_24rem] lg:items-start">
        <div>
          {compact ? (
            <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-card">
              <OrgTreeList
                nodes={showArchived ? nodes : nodes.filter((n) => n.is_active || n.kind === "COMPANY")}
                selectedId={selectedId}
                onSelect={(node: OrgNode) => setSelectedId(node.id)}
              />
            </div>
          ) : (
            <OrgChart
              nodes={nodes}
              company={company.data}
              showArchived={showArchived}
              selectedId={selectedId}
              onSelect={(node) => setSelectedId(node.id)}
            />
          )}
        </div>

        {selected ? (
          <NodePanel node={selected} nodes={nodes} onClose={() => setSelectedId(null)} onStructureChanged={structureChanged} />
        ) : (
          <EmptyState
            icon={<MousePointerClick />}
            title="یک گره را انتخاب کنید"
            message="یک حوزه، واحد یا بخش را انتخاب کنید تا افراد و جزئیات آن را ببینید."
            className="lg:sticky lg:top-4"
          />
        )}
      </div>
    </div>
  );
}
