"use client";

import { useState } from "react";
import { ApiError, apiPost } from "@/lib/api-client";
import { type OrgNode, type Person } from "@/lib/organization";
import { EMPTY_PLACEMENT, UNASSIGNED_PATH, hasPlacement, membershipBody, type PlacementForm } from "@/lib/personnel-org";
import type { Paginated } from "@/lib/types";
import { useApiQuery } from "@/lib/use-api-query";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
import { PlacementCascade } from "@/components/personnel/PlacementCascade";

/** People with no place in the chart yet, each with the same حوزه → واحد → بخش cascade as
 *  `PersonnelForm` — the quick way to give existing personnel (the importer's, or registered
 *  before the chart existed) a بخش. */
export function UnassignedPeople({ nodes, reload, onPlaced }: { nodes: OrgNode[]; reload: number; onPlaced: () => void }) {
  const people = useApiQuery<Paginated<Person>>(UNASSIGNED_PATH, reload);
  const [choice, setChoice] = useState<Record<number, PlacementForm>>({});
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (people.loading) return <LoadingBanner />;
  if (people.error) return <ErrorBanner message={people.error} />;
  const rows = people.data?.results ?? [];
  if (rows.length === 0) return null;

  function placementOf(personId: number): PlacementForm {
    return choice[personId] ?? EMPTY_PLACEMENT;
  }

  async function place(person: Person) {
    const body = membershipBody(person.id, nodes, placementOf(person.id));
    if (!body) return;
    setBusy(person.id);
    setError(null);
    try {
      await apiPost("/org/memberships/", body);
      setChoice((c) => {
        const next = { ...c };
        delete next[person.id];
        return next;
      });
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
      <ul className="space-y-3">
        {rows.map((person) => (
          <li key={person.id} className="space-y-2 rounded border border-slate-100 bg-slate-50 px-3 py-2 text-sm">
            <span className="block min-w-0">
              <span className="block truncate font-medium text-slate-900">{person.full_name}</span>
              <span className="block truncate text-xs text-slate-500">{person.title}</span>
            </span>
            <PlacementCascade
              nodes={nodes}
              value={placementOf(person.id)}
              onChange={(next) => setChoice((c) => ({ ...c, [person.id]: next }))}
            />
            <button
              type="button"
              disabled={!hasPlacement(nodes, placementOf(person.id)) || busy === person.id}
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
