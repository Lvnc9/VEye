"use client";

import { useState } from "react";
import { ApiError, apiPost } from "@/lib/api-client";
import { nodeOptions, type OrgNode, type Person } from "@/lib/organization";
import { UNASSIGNED_PATH, membershipBody } from "@/lib/personnel-org";
import type { Paginated } from "@/lib/types";
import { useApiQuery } from "@/lib/use-api-query";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";

/** People with no place in the chart yet, each with a select and «قرار بده» — the quick way to give
 *  existing personnel (the importer's, or registered before the chart existed) a بخش. */
export function UnassignedPeople({ nodes, reload, onPlaced }: { nodes: OrgNode[]; reload: number; onPlaced: () => void }) {
  const people = useApiQuery<Paginated<Person>>(UNASSIGNED_PATH, reload);
  const options = nodeOptions(nodes);
  const [choice, setChoice] = useState<Record<number, number>>({});
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (people.loading) return <LoadingBanner />;
  if (people.error) return <ErrorBanner message={people.error} />;
  const rows = people.data?.results ?? [];
  if (rows.length === 0 || options.length === 0) return null;

  async function place(person: Person) {
    const nodeId = choice[person.id];
    if (!nodeId) return;
    setBusy(person.id);
    setError(null);
    try {
      await apiPost("/org/memberships/", membershipBody(person.id, { nodeId, isLead: false, positionLabel: "" }));
      onPlaced();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "قرار دادن ممکن نشد.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section aria-label="افراد بدون جایگاه سازمانی" className="space-y-3 rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <div>
        <h2 className="text-base font-semibold text-slate-900">افراد بدون جایگاه سازمانی</h2>
        <p className="mt-1 text-xs text-slate-500">تا جایی در ساختار نداشته باشند، در هیچ بخشی دیده نمی‌شوند.</p>
      </div>
      {error && <ErrorBanner message={error} />}
      <ul className="space-y-2">
        {rows.map((person) => (
          <li key={person.id} className="flex flex-wrap items-center gap-2 rounded border border-slate-100 bg-slate-50 px-3 py-2 text-sm">
            <span className="min-w-0 flex-1">
              <span className="block truncate font-medium text-slate-900">{person.full_name}</span>
              <span className="block truncate text-xs text-slate-500">{person.title}</span>
            </span>
            <select
              aria-label={`گره ${person.full_name}`}
              value={choice[person.id] ?? ""}
              onChange={(e) => setChoice((c) => ({ ...c, [person.id]: Number(e.target.value) }))}
              className="max-w-56 rounded border border-slate-300 bg-white px-2 py-1.5 text-xs"
            >
              <option value="">انتخاب گره…</option>
              {options.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              disabled={!choice[person.id] || busy === person.id}
              onClick={() => place(person)}
              className="rounded bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-700 disabled:opacity-50"
            >
              قرار بده
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
