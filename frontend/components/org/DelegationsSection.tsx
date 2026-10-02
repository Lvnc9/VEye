"use client";

import { useState } from "react";
import { ApiError, apiDelete, apiPost } from "@/lib/api-client";
import { formatJalali } from "@/lib/jalali";
import type { Delegation, OrgNode, Person } from "@/lib/organization";
import type { Paginated } from "@/lib/types";
import { useApiQuery } from "@/lib/use-api-query";
import { ErrorBanner } from "@/components/StatusBanner";
import { JalaliDatePicker } from "@/components/JalaliDatePicker";
import { Avatar } from "@/components/ui/Avatar";
import { buttonClass } from "@/components/ui/Button";
import { controlClass } from "@/components/ui/Field";
import { IconButton } from "@/components/ui/IconButton";
import { Check, Search, UserCheck, UserX } from "lucide-react";

const smallButton = buttonClass({ variant: "secondary", size: "sm" });

/** Today as ISO in the browser's own zone (the date pickers' lower bound). */
function todayIso(): string {
  return new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

/**
 * «جانشین موقت» (Phase 16): who covers this node while its مسئول is away. NodePanel renders it only
 * for someone who can manage the node's members (the same rule the server checks), so the list is
 * not even fetched for everyone else. While a window is open the delegate
 * counts as a lead of the node and everything under it; nothing else about the chart changes.
 */
export function DelegationsSection({ node }: { node: OrgNode }) {
  const [reload, setReload] = useState(0);
  const delegations = useApiQuery<Paginated<Delegation>>(`/org/delegations/?node=${node.id}&page_size=50`, reload);
  const [delegate, setDelegate] = useState<Person | null>(null);
  const [query, setQuery] = useState("");
  const [from, setFrom] = useState(todayIso());
  const [to, setTo] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const rows = delegations.data?.results ?? [];

  async function add() {
    if (!delegate || !from || !to) return;
    setBusy(true);
    setError(null);
    try {
      await apiPost("/org/delegations/", { node: node.id, delegate: delegate.id, starts_on: from, ends_on: to, note });
      setDelegate(null);
      setQuery("");
      setTo("");
      setNote("");
      setReload((n) => n + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعیین جانشین ممکن نشد.");
    } finally {
      setBusy(false);
    }
  }

  async function end(delegation: Delegation) {
    setError(null);
    try {
      await apiDelete(`/org/delegations/${delegation.id}/`);
      setReload((n) => n + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "پایان جانشینی ممکن نشد.");
    }
  }

  return (
    <section aria-label="جانشین موقت" className="space-y-3 border-t border-slate-100 pt-4">
      <h3 className="flex items-center gap-2 text-sm font-bold text-slate-800">
        <UserCheck className="size-4 text-brand-600" />
        جانشین موقت
      </h3>
      <p className="text-[11px] leading-5 text-slate-500">
        در بازهٔ انتخاب‌شده، جانشین مانند مسئول این گره (و زیرمجموعه‌های آن) عمل می‌کند و پس از پایان بازه خودکار برمی‌گردد.
      </p>
      {error && <ErrorBanner message={error} />}

      {rows.length > 0 && (
        <ul className="space-y-2">
          {rows.map((row) => (
            <li key={row.id} className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm">
              <Avatar name={row.delegate_name} size="sm" />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-slate-900">{row.delegate_name}</span>
                <span className="block text-xs text-slate-500">
                  {formatJalali(row.starts_on)} تا {formatJalali(row.ends_on)}
                  {row.is_active ? " · در حال جانشینی" : " · آینده"}
                  {row.note && ` · ${row.note}`}
                </span>
              </span>
              <IconButton label={`پایان جانشینی ${row.delegate_name}`} tone="danger" size="sm" onClick={() => end(row)}>
                <UserX />
              </IconButton>
            </li>
          ))}
        </ul>
      )}

      <div className="space-y-2">
        {delegate ? (
          <p className="flex items-center gap-2 rounded-xl bg-brand-50 px-3 py-2 text-sm text-brand-900">
            <Check className="size-4" />
            {delegate.full_name}
            <button type="button" onClick={() => setDelegate(null)} className="ms-auto text-xs underline">
              تغییر
            </button>
          </p>
        ) : (
          <>
            <div className="relative">
              <Search className="pointer-events-none absolute inset-y-0 right-3 my-auto size-4 text-slate-400" />
              <input
                aria-label="جست‌وجوی جانشین"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="نام جانشین (دست‌کم دو حرف)"
                className={`${controlClass} h-10 w-full pr-9 pl-3 text-sm`}
              />
            </div>
            {query.trim().length >= 2 && <PersonResults key={query} query={query} onPick={setDelegate} />}
          </>
        )}
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="mb-1 block text-xs text-slate-600" htmlFor={`deleg-from-${node.id}`}>از</label>
            <JalaliDatePicker id={`deleg-from-${node.id}`} value={from} onChange={(iso) => setFrom(iso ?? "")} min={todayIso()} required />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-600" htmlFor={`deleg-to-${node.id}`}>تا</label>
            <JalaliDatePicker id={`deleg-to-${node.id}`} value={to} onChange={(iso) => setTo(iso ?? "")} min={from || todayIso()} required />
          </div>
        </div>
        <input
          aria-label="توضیح (اختیاری)"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={255}
          placeholder="توضیح (اختیاری)، مثلاً مرخصی"
          className={`${controlClass} h-10 w-full px-3 text-sm`}
        />
        <button type="button" disabled={busy || !delegate || !from || !to} onClick={add} className={smallButton}>
          <UserCheck />
          تعیین جانشین
        </button>
      </div>
    </section>
  );
}

function PersonResults({ query, onPick }: { query: string; onPick: (person: Person) => void }) {
  const people = useApiQuery<Paginated<Person>>(`/org/people/?q=${encodeURIComponent(query)}&page_size=6`);
  if (people.loading) return <p className="text-xs text-slate-500">در حال جستجو...</p>;
  if (people.error) return <p className="text-xs text-rose-600">{people.error}</p>;
  const rows = people.data?.results ?? [];
  if (rows.length === 0) return <p className="text-xs text-slate-500">کسی با این نام پیدا نشد.</p>;
  return (
    <ul className="space-y-1.5">
      {rows.map((person) => (
        <li key={person.id}>
          <button
            type="button"
            onClick={() => onPick(person)}
            className="flex w-full items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-start text-sm transition-colors hover:border-slate-300"
          >
            <Avatar name={person.full_name} size="sm" />
            <span className="min-w-0 truncate">
              {person.full_name} <span className="text-xs text-slate-500">{person.title}</span>
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
