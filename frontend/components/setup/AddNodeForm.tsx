"use client";

import { useState, type FormEvent } from "react";
import { ApiError, apiDelete, apiPost } from "@/lib/api-client";
import type { OrgNode, OrgNodeKind } from "@/lib/organization";
import { DarkError, darkInput, primaryButton } from "./ui";

/** Add one node of `kind` under `parentId` — a name and a button. The ordinary `/org/nodes/` API,
 *  so the wizard has no code path of its own to secure. */
export function AddNodeForm({
  kind,
  parentId,
  placeholder,
  onChanged,
}: {
  kind: OrgNodeKind;
  parentId: number;
  placeholder: string;
  onChanged: () => void;
}) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await apiPost("/org/nodes/", { kind, name: name.trim(), parent: parentId });
      setName("");
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "افزودن ممکن نشد.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-2">
      <div className="flex gap-2">
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder={placeholder}
          aria-label={placeholder}
          maxLength={255}
          className={darkInput}
        />
        <button type="submit" disabled={busy || !name.trim()} className={`${primaryButton} shrink-0`}>
          افزودن
        </button>
      </div>
      {error && <DarkError message={error} />}
    </form>
  );
}

/** A small «حذف» for a node the user just added by mistake (only an empty node can be deleted). */
export function DeleteNodeButton({ node, onChanged }: { node: OrgNode; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      await apiDelete(`/org/nodes/${node.id}/`);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "حذف ممکن نشد.");
      setBusy(false);
    }
  }

  return (
    <span className="flex items-center gap-2">
      {error && <span className="text-xs text-red-300">{error}</span>}
      <button
        type="button"
        onClick={remove}
        disabled={busy}
        aria-label={`حذف ${node.name}`}
        className="rounded px-2 py-0.5 text-xs text-slate-400 hover:bg-red-500/15 hover:text-red-300 disabled:opacity-50"
      >
        حذف
      </button>
    </span>
  );
}
