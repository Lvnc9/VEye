"use client";

import { useState } from "react";
import { ChevronDown, MapPinPlus, UserRoundX } from "lucide-react";
import { ApiError, apiPost } from "@/lib/api-client";
import { type OrgNode, type Person } from "@/lib/organization";
import { EMPTY_PLACEMENT, UNASSIGNED_PATH, hasPlacement, membershipBody, type PlacementForm } from "@/lib/personnel-org";
import type { Paginated } from "@/lib/types";
import { useApiQuery } from "@/lib/use-api-query";
import { ErrorBanner } from "@/components/StatusBanner";
import { PlacementCascade } from "@/components/personnel/PlacementCascade";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { SkeletonLines } from "@/components/ui/Skeleton";
import { cx } from "@/components/ui/cx";

/** People with no place in the chart yet, each with the same حوزه → واحد → بخش cascade as
 *  `PersonnelForm` — the quick way to give existing personnel (the importer's, or registered
 *  before the chart existed) a بخش. Each person is a row that opens to its cascade. */
export function UnassignedPeople({ nodes, reload, onPlaced }: { nodes: OrgNode[]; reload: number; onPlaced: () => void }) {
  const people = useApiQuery<Paginated<Person>>(UNASSIGNED_PATH, reload);
  const [choice, setChoice] = useState<Record<number, PlacementForm>>({});
  const [openId, setOpenId] = useState<number | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (people.loading && !people.data) {
    return (
      <Card>
        <SkeletonLines rows={3} />
      </Card>
    );
  }
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
      setOpenId(null);
      onPlaced();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "قرار دادن ممکن نشد.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card aria-label="افراد بدون جایگاه سازمانی">
      <CardHeader
        title="افراد بدون جایگاه سازمانی"
        icon={<UserRoundX />}
        description="تا جایی در ساختار نداشته باشند، در هیچ بخشی دیده نمی‌شوند."
        actions={
          <span className="rounded-full bg-amber-50 px-2.5 py-0.5 text-xs text-amber-800 ring-1 ring-inset ring-amber-600/25 tabular-nums">
            {rows.length} نفر
          </span>
        }
      />
      {error && <ErrorBanner message={error} />}
      <ul className="grid gap-3 md:grid-cols-2">
        {rows.map((person, i) => {
          const open = openId === person.id;
          return (
            <li
              key={person.id}
              className={cx(
                "veye-stagger rounded-2xl border transition-[border-color,box-shadow] duration-200",
                open ? "border-brand-300 shadow-raised md:col-span-2" : "border-slate-200 hover:border-slate-300",
              )}
              style={{ "--i": Math.min(i, 8) } as React.CSSProperties}
            >
              <button
                type="button"
                aria-expanded={open}
                onClick={() => setOpenId(open ? null : person.id)}
                className="flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-right"
              >
                <Avatar name={person.full_name} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-bold text-slate-900">{person.full_name}</span>
                  <span className="block truncate text-xs text-slate-500">{person.title}</span>
                </span>
                <span className="inline-flex items-center gap-1 text-xs text-brand-700">
                  <MapPinPlus className="size-4" />
                  <span className="hidden sm:inline">جایگاه</span>
                  <ChevronDown className={cx("size-4 transition-transform duration-200", open && "rotate-180")} />
                </span>
              </button>
              {open && (
                <div className="space-y-4 border-t border-slate-100 px-4 pt-4 pb-4 animate-fade-in">
                  <PlacementCascade
                    nodes={nodes}
                    value={placementOf(person.id)}
                    onChange={(next) => setChoice((c) => ({ ...c, [person.id]: next }))}
                    bare
                  />
                  <div className="flex justify-end">
                    <Button
                      variant="primary"
                      icon={<MapPinPlus />}
                      disabled={!hasPlacement(nodes, placementOf(person.id))}
                      loading={busy === person.id}
                      onClick={() => place(person)}
                    >
                      قرار بده
                    </Button>
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
