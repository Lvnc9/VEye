"use client";

import { useState, type FormEvent } from "react";
import { ApiError, apiDelete, apiPatch, apiPost } from "@/lib/api-client";
import { useApiQuery } from "@/lib/use-api-query";
import {
  ORG_KIND_LABELS,
  ORG_KIND_TONE,
  childKindsOf,
  initials,
  memberCaption,
  pathLabel,
  type OrgMembership,
  type OrgNode,
  type OrgNodeKind,
  type Person,
} from "@/lib/organization";
import type { Paginated } from "@/lib/types";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";

const input = "w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm";
const smallButton = "rounded border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50 disabled:opacity-50";
const primary = "rounded bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-700 disabled:opacity-50";

/**
 * A node's side panel: where it sits, who is in it, and — only where the server says the viewer may —
 * how to change it. The `can_*` flags come from the same functions the write endpoints enforce, so a
 * button shown here is a request the server accepts.
 */
export function NodePanel({
  node,
  nodes,
  onClose,
  onStructureChanged,
}: {
  node: OrgNode;
  nodes: OrgNode[];
  onClose: () => void;
  onStructureChanged: (next?: { selectId?: number | null }) => void;
}) {
  return (
    <aside aria-label={`جزئیات ${node.name}`} className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <header className="flex items-start justify-between gap-3">
        <div>
          <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${ORG_KIND_TONE[node.kind]}`}>{ORG_KIND_LABELS[node.kind]}</span>
          <h2 className="mt-1 text-lg font-bold text-slate-900">
            {node.name}
            {!node.is_active && <span className="ms-2 text-xs font-normal text-amber-700">(بایگانی‌شده)</span>}
          </h2>
          <p className="mt-0.5 text-xs text-slate-500">{pathLabel(nodes, node.id)}</p>
        </div>
        <button type="button" onClick={onClose} aria-label="بستن" className="rounded px-2 py-1 text-slate-500 hover:bg-slate-100">
          ✕
        </button>
      </header>

      <Members node={node} />
      {(node.can_add_child || node.can_edit) && <StructureActions node={node} onChanged={onStructureChanged} />}
    </aside>
  );
}

// ---------------------------------------------------------------------------
// People
// ---------------------------------------------------------------------------

function Members({ node }: { node: OrgNode }) {
  const [reload, setReload] = useState(0);
  const members = useApiQuery<Paginated<OrgMembership>>(`/org/nodes/${node.id}/members/?page_size=200`, reload);
  const [error, setError] = useState<string | null>(null);
  const refresh = () => setReload((n) => n + 1);

  async function act(action: () => Promise<unknown>, fallback: string) {
    setError(null);
    try {
      await action();
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : fallback);
    }
  }

  const rows = members.data?.results ?? [];
  return (
    <section aria-label="افراد" className="space-y-3">
      <h3 className="text-sm font-semibold text-slate-800">
        افراد {members.data ? <span className="font-normal text-slate-500">({members.data.count})</span> : null}
      </h3>
      {error && <ErrorBanner message={error} />}
      {members.loading ? (
        <LoadingBanner />
      ) : members.error ? (
        <ErrorBanner message={members.error} />
      ) : rows.length === 0 ? (
        <p className="rounded-lg border border-dashed border-slate-300 px-3 py-4 text-center text-xs text-slate-500">هنوز کسی در این گره نیست.</p>
      ) : (
        <ul className="space-y-2">
          {rows.map((m) => (
            <li key={m.id} className="flex items-center gap-3 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
              <span aria-hidden className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-800 text-xs font-bold text-white">
                {initials(m.user_name)}
              </span>
              <div className="min-w-0 flex-1 text-sm">
                <p className="truncate font-medium text-slate-900">
                  {m.user_name}
                  {m.is_lead && <span className="ms-2 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-800">مسئول</span>}
                </p>
                <p className="truncate text-xs text-slate-500">{[m.user_title, memberCaption(m, node.name)].filter(Boolean).join(" · ")}</p>
              </div>
              {node.can_manage_members && (
                <div className="flex shrink-0 gap-1">
                  <button
                    type="button"
                    className={smallButton}
                    onClick={() => act(() => apiPatch(`/org/memberships/${m.id}/`, { is_lead: !m.is_lead }), "تغییر مسئولیت ممکن نشد.")}
                  >
                    {m.is_lead ? "برداشتن مسئولیت" : "مسئول کن"}
                  </button>
                  <button
                    type="button"
                    className={`${smallButton} text-red-700`}
                    aria-label={`حذف ${m.user_name} از ${node.name}`}
                    onClick={() => act(() => apiDelete(`/org/memberships/${m.id}/`), "حذف عضو ممکن نشد.")}
                  >
                    حذف
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {node.can_manage_members && node.is_active && (
        <AddMember node={node} memberIds={new Set(rows.map((m) => m.user))} onAdded={refresh} onError={setError} />
      )}
    </section>
  );
}

function AddMember({ node, memberIds, onAdded, onError }: { node: OrgNode; memberIds: Set<number>; onAdded: () => void; onError: (message: string | null) => void }) {
  const [term, setTerm] = useState("");
  const query = term.trim();

  return (
    <div className="space-y-2 border-t border-slate-100 pt-3">
      <label className="block text-xs font-medium text-slate-600" htmlFor={`add-member-${node.id}`}>
        افزودن فرد به {node.name}
      </label>
      <input
        id={`add-member-${node.id}`}
        value={term}
        onChange={(event) => setTerm(event.target.value)}
        placeholder="جستجوی نام (دست‌کم دو حرف)"
        className={input}
      />
      {query.length >= 2 && (
        <PeopleResults key={query} query={query} node={node} memberIds={memberIds} onAdded={() => { setTerm(""); onAdded(); }} onError={onError} />
      )}
    </div>
  );
}

function PeopleResults({ query, node, memberIds, onAdded, onError }: { query: string; node: OrgNode; memberIds: Set<number>; onAdded: () => void; onError: (message: string | null) => void }) {
  const people = useApiQuery<Paginated<Person>>(`/org/people/?q=${encodeURIComponent(query)}&page_size=8`);
  const [busy, setBusy] = useState<number | null>(null);

  async function add(person: Person) {
    setBusy(person.id);
    onError(null);
    try {
      await apiPost("/org/memberships/", { user: person.id, node: node.id });
      onAdded();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "افزودن ممکن نشد.");
    } finally {
      setBusy(null);
    }
  }

  if (people.loading) return <p className="text-xs text-slate-500">در حال جستجو...</p>;
  if (people.error) return <p className="text-xs text-red-600">{people.error}</p>;
  const rows = people.data?.results ?? [];
  if (rows.length === 0) return <p className="text-xs text-slate-500">کسی با این نام پیدا نشد.</p>;

  return (
    <ul className="space-y-1">
      {rows.map((person) => {
        const already = memberIds.has(person.id);
        const places = person.memberships.map((m) => m.node_name).join("، ");
        return (
          <li key={person.id} className="flex items-center justify-between gap-2 rounded border border-slate-100 px-3 py-1.5 text-sm">
            <span className="min-w-0">
              <span className="block truncate">{person.full_name}</span>
              <span className="block truncate text-[11px] text-slate-500">{[person.title, places].filter(Boolean).join(" · ") || "بدون جایگاه سازمانی"}</span>
            </span>
            <button type="button" disabled={already || busy === person.id} onClick={() => add(person)} className={primary}>
              {already ? "عضو است" : "افزودن"}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

// ---------------------------------------------------------------------------
// Structure
// ---------------------------------------------------------------------------

function StructureActions({ node, onChanged }: { node: OrgNode; onChanged: (next?: { selectId?: number | null }) => void }) {
  const childKinds = childKindsOf(node.kind);
  const [kind, setKind] = useState<OrgNodeKind>(childKinds[0] ?? "UNIT");
  const [name, setName] = useState("");
  const [rename, setRename] = useState(node.name);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState<"delete" | "archive" | null>(null);

  async function run(action: () => Promise<unknown>, fallback: string, next?: { selectId?: number | null }) {
    setBusy(true);
    setError(null);
    try {
      await action();
      onChanged(next);
      return true;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : fallback);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function addChild(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    if (await run(() => apiPost("/org/nodes/", { kind, name: name.trim(), parent: node.id }), "افزودن ممکن نشد.")) setName("");
  }

  async function saveName(event: FormEvent) {
    event.preventDefault();
    if (!rename.trim() || rename.trim() === node.name) return;
    await run(() => apiPatch(`/org/nodes/${node.id}/`, { name: rename.trim() }), "تغییر نام ممکن نشد.");
  }

  return (
    <section aria-label="ساختار" className="space-y-4 border-t border-slate-100 pt-4">
      <h3 className="text-sm font-semibold text-slate-800">ساختار</h3>
      {error && <ErrorBanner message={error} />}

      {node.can_add_child && node.is_active && childKinds.length > 0 && (
        <form onSubmit={addChild} className="space-y-2">
          <label className="block text-xs font-medium text-slate-600" htmlFor={`child-name-${node.id}`}>
            افزودن به {node.name}
          </label>
          <div className="flex gap-2">
            {childKinds.length > 1 && (
              <select aria-label="نوع" value={kind} onChange={(e) => setKind(e.target.value as OrgNodeKind)} className="rounded border border-slate-300 bg-white px-2 text-sm">
                {childKinds.map((k) => (
                  <option key={k} value={k}>
                    {ORG_KIND_LABELS[k]}
                  </option>
                ))}
              </select>
            )}
            <input
              id={`child-name-${node.id}`}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={`نام ${ORG_KIND_LABELS[childKinds.length > 1 ? kind : childKinds[0]]}`}
              maxLength={255}
              className={input}
            />
            <button type="submit" disabled={busy || !name.trim()} className={primary}>
              افزودن
            </button>
          </div>
        </form>
      )}

      {node.can_edit && (
        <>
          <form onSubmit={saveName} className="flex gap-2">
            <input aria-label="نام" value={rename} onChange={(e) => setRename(e.target.value)} maxLength={255} className={input} />
            <button type="submit" disabled={busy || !rename.trim() || rename.trim() === node.name} className={smallButton}>
              تغییر نام
            </button>
          </form>

          {node.kind !== "COMPANY" && (
            <div className="flex flex-wrap gap-2">
              {node.is_active ? (
                <button type="button" disabled={busy} onClick={() => setConfirming("archive")} className={smallButton}>
                  بایگانی
                </button>
              ) : (
                <button type="button" disabled={busy} onClick={() => run(() => apiPost(`/org/nodes/${node.id}/unarchive/`), "بازگردانی ممکن نشد.")} className={smallButton}>
                  بازگردانی از بایگانی
                </button>
              )}
              <button type="button" disabled={busy} onClick={() => setConfirming("delete")} className={`${smallButton} text-red-700`}>
                حذف
              </button>
            </div>
          )}
        </>
      )}

      {confirming === "archive" && (
        <ConfirmDialog
          title={`بایگانی ${node.name}`}
          message="گره بایگانی‌شده از نمودار پنهان می‌شود و چیزی به آن افزوده نمی‌شود، اما افراد و سوابق آن می‌مانند. هر زمان می‌توانید آن را بازگردانید. ابتدا باید زیرمجموعه‌های فعال آن بایگانی شده باشند."
          confirmLabel="بایگانی"
          onCancel={() => setConfirming(null)}
          onConfirm={async () => {
            await apiPost(`/org/nodes/${node.id}/archive/`);
            setConfirming(null);
            onChanged();
          }}
        />
      )}
      {confirming === "delete" && (
        <ConfirmDialog
          title={`حذف ${node.name}`}
          message="حذف برگشت‌پذیر نیست و فقط برای گرهٔ خالی (بدون زیرمجموعه و عضو) ممکن است. اگر سابقه‌ای دارد، به‌جای حذف آن را بایگانی کنید."
          confirmLabel="حذف"
          danger
          onCancel={() => setConfirming(null)}
          onConfirm={async () => {
            await apiDelete(`/org/nodes/${node.id}/`);
            setConfirming(null);
            onChanged({ selectId: node.parent });
          }}
        />
      )}
    </section>
  );
}
