"use client";

import { useState } from "react";
import type { Person } from "@/lib/organization";
import type { Paginated } from "@/lib/types";
import { useApiQuery } from "@/lib/use-api-query";
import { Avatar } from "@/components/ui/Avatar";
import { buttonClass } from "@/components/ui/Button";
import { controlClass } from "@/components/ui/Field";
import { Check, Search, UserPlus } from "lucide-react";

/**
 * Find a person by name and pick them: a search box and, from two letters on, the matching people
 * (`GET /org/people/?q=`), each with a button. Was copied three times (the project's member panel,
 * its creation form's guest search, and the delegation section) before the quality module needed it a
 * fourth time.
 *
 * The box clears itself after a pick — every caller wanted that — and people in `excludedIds` stay in
 * the list with their button disabled and labelled `doneLabel`, so it is clear *why* they cannot be
 * picked again rather than the row vanishing. A visible `label` is optional; without one, pass
 * `ariaLabel` so the box still has a name.
 */
export function PersonPicker({
  id,
  label,
  ariaLabel,
  placeholder = "جست و جوی نام (دست‌کم دو حرف)",
  excludedIds,
  onPick,
  pickLabel = "افزودن",
  doneLabel = "افزوده شد",
}: {
  id: string;
  label?: string;
  ariaLabel?: string;
  placeholder?: string;
  excludedIds?: ReadonlySet<number>;
  onPick: (person: Person) => void;
  pickLabel?: string;
  doneLabel?: string;
}) {
  const [query, setQuery] = useState("");

  return (
    <div>
      {label && (
        <label htmlFor={id} className="mb-1.5 block text-xs text-slate-500">
          {label}
        </label>
      )}
      <div className="relative">
        <Search className="pointer-events-none absolute inset-y-0 right-3 my-auto size-4 text-slate-400" />
        <input
          id={id}
          aria-label={label ? undefined : ariaLabel}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder}
          className={`${controlClass} h-10 w-full pr-9 pl-3 text-sm`}
        />
      </div>
      {query.trim().length >= 2 && (
        <PersonResults
          key={query}
          query={query}
          excludedIds={excludedIds}
          pickLabel={pickLabel}
          doneLabel={doneLabel}
          onPick={(person) => {
            setQuery("");
            onPick(person);
          }}
        />
      )}
    </div>
  );
}

function PersonResults({
  query,
  excludedIds,
  pickLabel,
  doneLabel,
  onPick,
}: {
  query: string;
  excludedIds?: ReadonlySet<number>;
  pickLabel: string;
  doneLabel: string;
  onPick: (person: Person) => void;
}) {
  const people = useApiQuery<Paginated<Person>>(`/org/people/?q=${encodeURIComponent(query)}&page_size=8`);
  if (people.loading) return <p className="mt-2 text-xs text-slate-500">در حال جستجو...</p>;
  if (people.error) return <p className="mt-1 text-xs text-rose-600">{people.error}</p>;
  const rows = people.data?.results ?? [];
  if (rows.length === 0) return <p className="mt-1 text-xs text-slate-500">کسی با این نام پیدا نشد.</p>;
  return (
    <ul className="mt-2 space-y-1.5 animate-fade-in">
      {rows.map((person) => {
        const already = excludedIds?.has(person.id) ?? false;
        return (
          <li
            key={person.id}
            className="flex items-center justify-between gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm transition-colors hover:border-slate-300"
          >
            <span className="flex min-w-0 items-center gap-2">
              <Avatar name={person.full_name} size="sm" />
              <span className="min-w-0 truncate">
                {person.full_name} <span className="text-xs text-slate-500">{person.title}</span>
              </span>
            </span>
            <button
              type="button"
              disabled={already}
              onClick={() => onPick(person)}
              className={buttonClass({ variant: "secondary", size: "xs", className: "shrink-0" })}
            >
              {already ? <Check /> : <UserPlus />}
              {already ? doneLabel : pickLabel}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
