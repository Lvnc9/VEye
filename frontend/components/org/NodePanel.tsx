"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ApiError, apiDelete, apiPatch, apiPost } from "@/lib/api-client";
import { canOpenNodeChannel, type Conversation } from "@/lib/chat";
import { useCurrentUser } from "@/lib/current-user";
import { useApiQuery } from "@/lib/use-api-query";
import {
  ORG_KIND_LABELS,
  ORG_KIND_TONE,
  ancestorsOf,
  childKindsOf,
  describeNodeBlockers,
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
import { buttonClass } from "@/components/ui/Button";
import { controlClass } from "@/components/ui/Field";
import { Archive, ArchiveRestore, Crown, MessageCircle, MessagesSquare, Network, PencilLine, Plus, Search, Trash2, UserPlus, Users, X } from "lucide-react";
import { cx } from "@/components/ui/cx";
import { Avatar } from "@/components/ui/Avatar";
import { IconButton } from "@/components/ui/IconButton";

const input = `${controlClass} w-full px-3 py-2 text-sm`;

const KIND_BAND: Record<OrgNodeKind, string> = {
  COMPANY: "bg-gradient-to-l from-slate-700 to-slate-900",
  DOMAIN: "bg-gradient-to-l from-indigo-400 to-indigo-600",
  UNIT: "bg-gradient-to-l from-brand-400 to-brand-600",
  SECTION: "bg-gradient-to-l from-emerald-400 to-emerald-600",
};
const smallButton = buttonClass({ variant: "secondary", size: "sm" });
const primary = buttonClass({ variant: "primary", size: "sm" });

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
    <aside
      key={node.id}
      aria-label={`جزئیات ${node.name}`}
      className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-card animate-fade-in lg:sticky lg:top-4"
    >
      {/* A band in the node kind's colour. */}
      <div aria-hidden className={cx("h-1.5", KIND_BAND[node.kind])} />
      <div className="space-y-5 p-5">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <span className={`rounded-full px-2 py-0.5 text-[10px] ${ORG_KIND_TONE[node.kind]}`}>{ORG_KIND_LABELS[node.kind]}</span>
          <h2 className="mt-1.5 truncate text-lg font-bold text-slate-900">
            {node.name}
            {!node.is_active && <span className="ms-2 text-xs font-normal text-amber-700">(بایگانی‌شده)</span>}
          </h2>
          <p className="mt-0.5 text-xs text-slate-500">{pathLabel(nodes, node.id)}</p>
        </div>
        <IconButton label="بستن" onClick={onClose} size="sm" className="-me-1">
          <X />
        </IconButton>
      </header>

      <GroupChat node={node} nodes={nodes} />
      <Members node={node} />
      {(node.can_add_child || node.can_edit) && <StructureActions node={node} onChanged={onStructureChanged} />}
      </div>
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Chat: open a conversation and land in the کارتابل
// ---------------------------------------------------------------------------

/** POST, then go to /inbox?c=<id>. Returns an error message, or null on success. */
function useOpenChat() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  async function open(path: string, body: object, fallback: string): Promise<string | null> {
    setBusy(true);
    try {
      const conversation = await apiPost<Conversation>(path, body);
      router.push(`/inbox?c=${conversation.id}`);
      return null;
    } catch (err) {
      setBusy(false);
      return err instanceof ApiError ? err.message : fallback;
    }
  }
  return { open, busy };
}

/** «گفتگوی گروه» — shown only where the server would let the viewer in (the rule mirrored in
 *  lib/chat.ts for affordance; the server still decides). */
function GroupChat({ node, nodes }: { node: OrgNode; nodes: OrgNode[] }) {
  const { user } = useCurrentUser();
  const { open, busy } = useOpenChat();
  const [error, setError] = useState<string | null>(null);
  const ancestorIds = ancestorsOf(nodes, node.id).map((n) => n.id);
  if (!user || !canOpenNodeChannel(node, ancestorIds, user.memberships ?? [])) return null;
  return (
    <div className="space-y-2">
      <button
        type="button"
        disabled={busy}
        onClick={async () => setError(await open("/chat/conversations/node/", { node: node.id }, "باز کردن گفتگو ممکن نشد."))}
        className={cx(primary, "h-10 w-full")}
      >
        <MessagesSquare />
        {node.kind === "COMPANY" ? "گفتگوی همهٔ شرکت" : `گفتگوی گروه ${node.name}`}
      </button>
      {node.kind !== "COMPANY" && (
        <p className="text-[11px] text-slate-500">این گفتگو برای مسئولان گره‌های بالادستی نیز قابل مشاهده است.</p>
      )}
      {error && <ErrorBanner message={error} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// People
// ---------------------------------------------------------------------------

function Members({ node }: { node: OrgNode }) {
  const { user } = useCurrentUser();
  const chat = useOpenChat();
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
      <h3 className="flex items-center gap-2 text-sm font-bold text-slate-800">
        <Users className="size-4 text-brand-600" />
        افراد
        {members.data && (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-normal text-slate-600 tabular-nums">{members.data.count}</span>
        )}
      </h3>
      {error && <ErrorBanner message={error} />}
      {members.loading ? (
        <LoadingBanner />
      ) : members.error ? (
        <ErrorBanner message={members.error} />
      ) : rows.length === 0 ? (
        <p className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-slate-300 px-3 py-5 text-center text-xs text-slate-500">
          <Users className="size-5 text-slate-300" />
          هنوز کسی در این گره نیست.
        </p>
      ) : (
        <ul className="space-y-2">
          {rows.map((m) => (
            <li key={m.id} className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl border border-slate-200 bg-white px-3 py-2 transition-colors hover:border-slate-300">
              <Avatar name={m.user_name} />
              <div className="min-w-[9rem] flex-1 text-sm">
                <p className="truncate font-bold text-slate-900">
                  {m.user_name}
                  {m.is_lead && (
                    <span className="ms-2 inline-flex items-center gap-0.5 rounded-full bg-amber-50 px-2 py-0.5 text-[10px] text-amber-800 ring-1 ring-inset ring-amber-600/25">
                      <Crown className="size-3" />
                      مسئول
                    </span>
                  )}
                </p>
                <p className="truncate text-xs text-slate-500">{[m.user_title, memberCaption(m, node.name)].filter(Boolean).join(" · ")}</p>
              </div>
              <div className="flex shrink-0 items-center gap-0.5">
                {user && m.user !== user.id && m.user_is_active && (
                  <IconButton
                    label={`گفتگو با ${m.user_name}`}
                    tone="brand"
                    size="sm"
                    disabled={chat.busy}
                    onClick={async () =>
                      setError(await chat.open("/chat/conversations/direct/", { user: m.user }, "باز کردن گفتگو ممکن نشد."))
                    }
                  >
                    <MessageCircle />
                  </IconButton>
                )}
                {node.can_manage_members && (
                  <>
                    <IconButton
                      label={m.is_lead ? "برداشتن مسئولیت" : "مسئول کن"}
                      size="sm"
                      aria-pressed={m.is_lead}
                      className={m.is_lead ? "text-amber-500 hover:bg-amber-50 hover:text-amber-600" : undefined}
                      onClick={() => act(() => apiPatch(`/org/memberships/${m.id}/`, { is_lead: !m.is_lead }), "تغییر مسئولیت ممکن نشد.")}
                    >
                      <Crown />
                    </IconButton>
                    <IconButton
                      label={`حذف ${m.user_name} از ${node.name}`}
                      tone="danger"
                      size="sm"
                      onClick={() => act(() => apiDelete(`/org/memberships/${m.id}/`), "حذف عضو ممکن نشد.")}
                    >
                      <Trash2 />
                    </IconButton>
                  </>
                )}
              </div>
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
      <label className="flex items-center gap-1.5 text-xs text-slate-600" htmlFor={`add-member-${node.id}`}>
        <UserPlus className="size-3.5" />
        افزودن فرد به {node.name}
      </label>
      <div className="relative">
        <Search className="pointer-events-none absolute inset-y-0 right-3 my-auto size-4 text-slate-400" />
        <input
          id={`add-member-${node.id}`}
          value={term}
          onChange={(event) => setTerm(event.target.value)}
          placeholder="جستجوی نام (دست‌کم دو حرف)"
          className={cx(input, "pr-9")}
        />
      </div>
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
  if (people.error) return <p className="text-xs text-rose-600">{people.error}</p>;
  const rows = people.data?.results ?? [];
  if (rows.length === 0) return <p className="text-xs text-slate-500">کسی با این نام پیدا نشد.</p>;

  return (
    <ul className="space-y-1.5 animate-fade-in">
      {rows.map((person) => {
        const already = memberIds.has(person.id);
        const places = person.memberships.map((m) => m.node_name).join("، ");
        return (
          <li key={person.id} className="flex items-center justify-between gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm transition-colors hover:border-slate-300">
            <span className="flex min-w-0 items-center gap-2">
              <Avatar name={person.full_name} size="sm" />
              <span className="min-w-0">
              <span className="block truncate">{person.full_name}</span>
              <span className="block truncate text-[11px] text-slate-500">{[person.title, places].filter(Boolean).join(" · ") || "بدون جایگاه سازمانی"}</span>
              </span>
            </span>
            <button type="button" disabled={already || busy === person.id} onClick={() => add(person)} className={primary}>
              {!already && <UserPlus />}
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
      <h3 className="flex items-center gap-2 text-sm font-bold text-slate-800">
        <Network className="size-4 text-brand-600" />
        ساختار
      </h3>
      {error && <ErrorBanner message={error} />}

      {node.can_add_child && node.is_active && childKinds.length > 0 && (
        <form onSubmit={addChild} className="space-y-2">
          <label className="block text-xs font-medium text-slate-600" htmlFor={`child-name-${node.id}`}>
            افزودن به {node.name}
          </label>
          <div className="flex gap-2">
            {childKinds.length > 1 && (
              <select aria-label="نوع" value={kind} onChange={(e) => setKind(e.target.value as OrgNodeKind)} className={`${controlClass} px-2 text-sm`}>
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
            <button type="submit" disabled={busy || !name.trim()} className={cx(primary, "h-auto shrink-0")}>
              <Plus />
              افزودن
            </button>
          </div>
        </form>
      )}

      {node.can_edit && (
        <>
          <form onSubmit={saveName} className="flex gap-2">
            <input aria-label="نام" value={rename} onChange={(e) => setRename(e.target.value)} maxLength={255} className={input} />
            <button
              type="submit"
              disabled={busy || !rename.trim() || rename.trim() === node.name}
              className={cx(smallButton, "h-auto shrink-0")}
            >
              <PencilLine />
              تغییر نام
            </button>
          </form>

          {node.kind !== "COMPANY" && (
            <div className="flex flex-wrap gap-2">
              {node.is_active ? (
                <button type="button" disabled={busy} onClick={() => setConfirming("archive")} className={smallButton}>
                  <Archive />
                  بایگانی
                </button>
              ) : (
                <button type="button" disabled={busy} onClick={() => run(() => apiPost(`/org/nodes/${node.id}/unarchive/`), "بازگردانی ممکن نشد.")} className={smallButton}>
                  <ArchiveRestore />
                  بازگردانی از بایگانی
                </button>
              )}
              <button
                type="button"
                disabled={busy}
                onClick={() => setConfirming("delete")}
                className={buttonClass({ variant: "danger-ghost", size: "sm" })}
              >
                <Trash2 />
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
            try {
              await apiDelete(`/org/nodes/${node.id}/`);
            } catch (err) {
              // 409 node_not_empty carries counts: say what is in the way, not only that something is.
              const blockers = err instanceof ApiError && err.status === 409 ? describeNodeBlockers(err.data) : null;
              if (err instanceof ApiError && blockers) throw new ApiError(`${err.message} (${blockers})`, err.status, err.data);
              throw err;
            }
            setConfirming(null);
            onChanged({ selectId: node.parent });
          }}
        />
      )}
    </section>
  );
}
