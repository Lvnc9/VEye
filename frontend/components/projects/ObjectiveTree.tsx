"use client";

import { useEffect, useState, type FormEvent } from "react";
import { ApiError, apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api-client";
import { formatJalali, formatJalaliDateTime } from "@/lib/jalali";
import {
  OBJECTIVE_STATUS_LABELS,
  OBJECTIVE_STATUS_TONE,
  objectiveAssigneeRows,
  olderUpdates,
  type Objective,
  type ObjectiveAssigneeRow,
  type ObjectiveStatus,
  type ObjectiveUpdate,
  type ProjectDetail,
  type ProjectMember,
} from "@/lib/projects";
import type { Paginated } from "@/lib/types";
import { useCurrentUser } from "@/lib/current-user";
import { draftKey, useLocalDraft } from "@/lib/local-draft";
import { ErrorBanner } from "@/components/StatusBanner";
import { JalaliDatePicker } from "@/components/JalaliDatePicker";
import { ObjectiveEditDialog } from "@/components/projects/ObjectiveEditDialog";
import { buttonClass } from "@/components/ui/Button";
import { controlClass } from "@/components/ui/Field";
import { ChevronDown, ChevronUp, Pencil } from "lucide-react";

const select = "h-7 rounded-lg border-0 px-2 text-xs transition-shadow focus:outline-none focus:ring-4 focus:ring-brand-500/15 disabled:opacity-60";
const input = `${controlClass} w-full px-3 py-2 text-sm`;

/** «اهداف» as a tree: each objective is the root, its assignees are the leaves (docs/12 §D). Drawn
 *  with plain CSS connector lines — RTL, no library, readable at 375px. */
export function ObjectiveTree({
  project,
  objectives,
  onChanged,
}: {
  project: ProjectDetail;
  objectives: Objective[];
  onChanged: () => void;
}) {
  const { user } = useCurrentUser();
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [editing, setEditing] = useState<Objective | null>(null);

  async function changeStatus(objective: Objective, status: ObjectiveStatus) {
    setError(null);
    setBusyId(objective.id);
    try {
      await apiPatch(`/projects/${project.id}/objectives/${objective.id}/`, { status });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تغییر وضعیت ممکن نشد.");
    } finally {
      setBusyId(null);
    }
  }

  async function move(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= objectives.length) return;
    const order = objectives.map((o) => o.id);
    [order[index], order[target]] = [order[target], order[index]];
    setError(null);
    try {
      await apiPost(`/projects/${project.id}/objectives/reorder/`, { order });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تغییر ترتیب ممکن نشد.");
    }
  }

  return (
    <section aria-label="اهداف" className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card sm:p-6">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-base font-bold text-slate-900">اهداف</h2>
        {project.can_edit && (
          <button type="button" onClick={() => setAdding((v) => !v)} className="text-sm text-brand-700 underline-offset-4 transition-colors hover:text-brand-800 hover:underline">
            {adding ? "بستن" : "افزودن ریزهدف"}
          </button>
        )}
      </div>
      {error && <ErrorBanner message={error} />}
      {adding && (
        <AddObjectiveForm
          project={project}
          onAdded={() => {
            setAdding(false);
            onChanged();
          }}
          onCancel={() => setAdding(false)}
        />
      )}
      {editing && (
        <ObjectiveEditDialog
          projectId={project.id}
          objective={editing}
          members={project.members}
          onSaved={() => {
            setEditing(null);
            onChanged();
          }}
          onCancel={() => setEditing(null)}
        />
      )}
      {objectives.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500">هنوز ریزهدفی افزوده نشده است.</p>
      ) : (
        <ul className="mt-3 space-y-4">
          {objectives.map((objective, index) => (
            <li
              key={objective.id}
              className={`rounded-xl border p-3.5 transition-colors ${objective.is_overdue ? "border-rose-200 bg-rose-50/60" : "border-slate-200 hover:border-slate-300"}`}
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-bold text-slate-900">{objective.title}</p>
                  {objective.description && <p className="mt-0.5 text-xs text-slate-600">{objective.description}</p>}
                  <p className="mt-1 text-xs text-slate-500">
                    مهلت: {formatJalali(objective.due_on)}
                    {objective.is_overdue && <span className="mr-1 font-medium text-rose-700">(دیرکرد)</span>}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  {objective.can_edit && (
                    <span className="flex flex-col">
                      <button
                        type="button"
                        aria-label="جابه‌جایی به بالا"
                        disabled={index === 0}
                        onClick={() => move(index, -1)}
                        className="flex h-4 w-6 items-center justify-center rounded text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-800 disabled:opacity-30"
                      >
                        <ChevronUp className="size-3.5" />
                      </button>
                      <button
                        type="button"
                        aria-label="جابه‌جایی به پایین"
                        disabled={index === objectives.length - 1}
                        onClick={() => move(index, 1)}
                        className="flex h-4 w-6 items-center justify-center rounded text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-800 disabled:opacity-30"
                      >
                        <ChevronDown className="size-3.5" />
                      </button>
                    </span>
                  )}
                  <select
                    aria-label={`وضعیت ${objective.title}`}
                    value={objective.status}
                    disabled={!objective.can_change_status || busyId === objective.id}
                    onChange={(e) => changeStatus(objective, e.target.value as ObjectiveStatus)}
                    className={`${select} ${OBJECTIVE_STATUS_TONE[objective.status]}`}
                  >
                    {(Object.keys(OBJECTIVE_STATUS_LABELS) as ObjectiveStatus[]).map((value) => (
                      <option key={value} value={value}>
                        {OBJECTIVE_STATUS_LABELS[value]}
                      </option>
                    ))}
                  </select>
                  {objective.can_edit && (
                    <>
                      <button
                        type="button"
                        onClick={() => setEditing(objective)}
                        className="inline-flex h-7 items-center gap-1 rounded-lg px-2 text-xs text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
                      >
                        <Pencil className="size-3.5" />
                        ویرایش
                      </button>
                      <RemoveObjectiveButton project={project} objective={objective} onRemoved={onChanged} onError={setError} />
                    </>
                  )}
                </div>
              </div>

              {objective.assignees.length > 0 && (
                <ul className="relative mt-3 me-1.5 space-y-3 border-s-2 border-slate-200 ps-4">
                  {objectiveAssigneeRows(objective, user?.id ?? null).map((row) => (
                    <li key={row.user} className="relative">
                      <span aria-hidden className="absolute top-4 h-px w-4 -start-4 bg-slate-200" />
                      <AssigneeLeaf projectId={project.id} objective={objective} row={row} onChanged={onChanged} onError={setError} />
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function RemoveObjectiveButton({
  project,
  objective,
  onRemoved,
  onError,
}: {
  project: ProjectDetail;
  objective: Objective;
  onRemoved: () => void;
  onError: (message: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  async function handleClick() {
    setBusy(true);
    try {
      await apiDelete(`/projects/${project.id}/objectives/${objective.id}/`);
      onRemoved();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "حذف ریزهدف ممکن نشد.");
      setBusy(false);
    }
  }
  return (
    <button
      type="button"
      disabled={busy}
      onClick={handleClick}
      aria-label={`حذف ${objective.title}`}
      className="inline-flex h-7 items-center rounded-lg px-2 text-xs text-rose-600 transition-colors hover:bg-rose-50 disabled:opacity-50"
    >
      حذف
    </button>
  );
}

/** One leaf: an assignee's name/سمت, their latest report, and — only on the viewer's own leaf — the
 *  controls to write or edit one. */
function AssigneeLeaf({
  projectId,
  objective,
  row,
  onChanged,
  onError,
}: {
  projectId: number;
  objective: Objective;
  row: ObjectiveAssigneeRow;
  onChanged: () => void;
  onError: (message: string) => void;
}) {
  const [writing, setWriting] = useState(false);
  const [editingLatest, setEditingLatest] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);

  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 p-2.5">
      <p className="text-sm font-medium text-slate-800">
        {row.name} <span className="font-normal text-slate-500">{row.title}</span>
      </p>

      {editingLatest && row.latestUpdate ? (
        <UpdateEditor
          projectId={projectId}
          objectiveId={objective.id}
          updateId={row.latestUpdate.id}
          initialBody={row.latestUpdate.body}
          onSaved={() => {
            setEditingLatest(false);
            onChanged();
          }}
          onCancel={() => setEditingLatest(false)}
          onError={onError}
        />
      ) : row.latestUpdate ? (
        <div className="mt-1">
          <p className="whitespace-pre-wrap text-sm text-slate-700">{row.latestUpdate.body}</p>
          <p className="mt-0.5 text-xs text-slate-500">{formatJalaliDateTime(row.latestUpdate.created_at)}</p>
        </div>
      ) : (
        <p className="mt-1 text-xs text-slate-500">هنوز گزارشی ثبت نشده است.</p>
      )}

      <div className="mt-1.5 flex flex-wrap items-center gap-3 text-xs">
        {row.canPostUpdate && !writing && (
          <button type="button" onClick={() => setWriting(true)} className="text-brand-700 underline-offset-4 transition-colors hover:text-brand-800 hover:underline">
            نوشتن گزارش
          </button>
        )}
        {row.canEditLatest && !editingLatest && (
          <button type="button" onClick={() => setEditingLatest(true)} className="text-brand-700 underline-offset-4 transition-colors hover:text-brand-800 hover:underline">
            ویرایش
          </button>
        )}
        {row.historyCount > 0 && (
          <button type="button" onClick={() => setHistoryOpen((v) => !v)} className="text-slate-500 underline hover:text-slate-800">
            {historyOpen ? "بستن سوابق" : `سوابق (${row.historyCount})`}
          </button>
        )}
      </div>

      {writing && (
        <UpdateComposer
          projectId={projectId}
          objectiveId={objective.id}
          onPosted={() => {
            setWriting(false);
            onChanged();
          }}
          onCancel={() => setWriting(false)}
          onError={onError}
        />
      )}

      {historyOpen && (
        <UpdateHistory projectId={projectId} objectiveId={objective.id} authorId={row.user} latestId={row.latestUpdate?.id} />
      )}
    </div>
  );
}

function UpdateComposer({
  projectId,
  objectiveId,
  onPosted,
  onCancel,
  onError,
}: {
  projectId: number;
  objectiveId: number;
  onPosted: () => void;
  onCancel: () => void;
  onError: (message: string) => void;
}) {
  const { user } = useCurrentUser();
  const [body, setBody, clearBody] = useLocalDraft(user ? draftKey(user.id, projectId, "objective-update", objectiveId) : null);
  const [saving, setSaving] = useState(false);

  async function submit() {
    if (!body.trim()) return;
    setSaving(true);
    try {
      await apiPost(`/projects/${projectId}/objectives/${objectiveId}/updates/`, { body: body.trim() });
      clearBody();
      onPosted();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "ثبت گزارش ممکن نشد.");
      setSaving(false);
    }
  }

  return (
    <div className="mt-2 space-y-1.5">
      <textarea
        autoFocus
        value={body}
        onChange={(e) => setBody(e.target.value)}
        maxLength={4000}
        rows={3}
        aria-label="متن گزارش"
        className={input}
      />
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancel} disabled={saving} className={buttonClass({ variant: "secondary", size: "xs" })}>
          انصراف
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={saving || !body.trim()}
          className={buttonClass({ variant: "primary", size: "xs" })}
        >
          {saving ? "در حال ثبت..." : "ثبت گزارش"}
        </button>
      </div>
    </div>
  );
}

function UpdateEditor({
  projectId,
  objectiveId,
  updateId,
  initialBody,
  onSaved,
  onCancel,
  onError,
}: {
  projectId: number;
  objectiveId: number;
  updateId: number;
  initialBody: string;
  onSaved: () => void;
  onCancel: () => void;
  onError: (message: string) => void;
}) {
  const [body, setBody] = useState(initialBody);
  const [saving, setSaving] = useState(false);

  async function submit() {
    if (!body.trim()) return;
    setSaving(true);
    try {
      await apiPatch(`/projects/${projectId}/objectives/${objectiveId}/updates/${updateId}/`, { body: body.trim() });
      onSaved();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "ویرایش گزارش ممکن نشد.");
      setSaving(false);
    }
  }

  return (
    <div className="mt-1 space-y-1.5">
      <textarea autoFocus value={body} onChange={(e) => setBody(e.target.value)} maxLength={4000} rows={3} aria-label="ویرایش گزارش" className={input} />
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancel} disabled={saving} className={buttonClass({ variant: "secondary", size: "xs" })}>
          انصراف
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={saving || !body.trim()}
          className={buttonClass({ variant: "primary", size: "xs" })}
        >
          {saving ? "در حال ذخیره..." : "ذخیره"}
        </button>
      </div>
    </div>
  );
}

/** «سوابق (n)»: every earlier entry by this assignee, paged, newest first. */
function UpdateHistory({
  projectId,
  objectiveId,
  authorId,
  latestId,
}: {
  projectId: number;
  objectiveId: number;
  authorId: number;
  latestId: number | undefined;
}) {
  const [rows, setRows] = useState<ObjectiveUpdate[] | null>(null);
  const [next, setNext] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    let cancelled = false;
    apiGet<Paginated<ObjectiveUpdate>>(`/projects/${projectId}/objectives/${objectiveId}/updates/`, { author: authorId })
      .then((page) => {
        if (cancelled) return;
        setRows(olderUpdates(page.results, latestId));
        setNext(page.next);
      })
      .catch((err) => !cancelled && setError(err instanceof ApiError ? err.message : "دریافت سوابق ممکن نشد."));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, objectiveId, authorId]);

  async function loadMore() {
    if (!next) return;
    setLoadingMore(true);
    try {
      const page = await apiGet<Paginated<ObjectiveUpdate>>(next);
      setRows((current) => [...(current ?? []), ...olderUpdates(page.results, latestId)]);
      setNext(page.next);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "دریافت سوابق ممکن نشد.");
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <div className="mt-2 space-y-2 border-t border-slate-200 pt-2">
      {error && <p className="text-xs text-rose-600">{error}</p>}
      {rows === null ? (
        <p className="text-xs text-slate-500">در حال بارگذاری...</p>
      ) : rows.length === 0 ? (
        <p className="text-xs text-slate-500">سابقهٔ دیگری نیست.</p>
      ) : (
        <ul className="space-y-2">
          {rows.map((row) => (
            <li key={row.id} className="text-sm">
              <p className="whitespace-pre-wrap text-slate-700">{row.body}</p>
              <p className="mt-0.5 text-xs text-slate-500">{formatJalaliDateTime(row.created_at)}</p>
            </li>
          ))}
        </ul>
      )}
      {next && (
        <button type="button" onClick={loadMore} disabled={loadingMore} className="text-xs text-slate-500 underline hover:text-slate-800">
          {loadingMore ? "در حال بارگذاری..." : "بارگذاری بیشتر"}
        </button>
      )}
    </div>
  );
}

function AddObjectiveForm({
  project,
  onAdded,
  onCancel,
}: {
  project: ProjectDetail;
  onAdded: () => void;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [assignees, setAssignees] = useState<number[]>([]);
  const [dueOn, setDueOn] = useState("");
  const [weight, setWeight] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function toggle(user: number) {
    setAssignees((current) => (current.includes(user) ? current.filter((u) => u !== user) : [...current, user]));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim() || assignees.length === 0 || !dueOn) {
      setError("عنوان، دست‌کم یک مسئول و مهلت الزامی است.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await apiPost(`/projects/${project.id}/objectives/`, {
        title: title.trim(),
        description: description.trim(),
        assignees,
        due_on: dueOn,
        weight,
      });
      onAdded();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "افزودن ریزهدف ممکن نشد.");
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="mb-3 space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
      {error && <ErrorBanner message={error} />}
      <div>
        <label className="mb-1 block text-xs text-slate-600" htmlFor="new-objective-title">
          عنوان
        </label>
        <input id="new-objective-title" value={title} onChange={(e) => setTitle(e.target.value)} className={input} />
      </div>
      <div>
        <label className="mb-1 block text-xs text-slate-600" htmlFor="new-objective-description">
          شرح (اختیاری)
        </label>
        <textarea
          id="new-objective-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
          className={input}
        />
      </div>
      <div>
        <span className="mb-1 block text-xs text-slate-600">مسئولان</span>
        {project.members.length === 0 ? (
          <p className="text-xs text-slate-500">این پروژه هنوز عضوی ندارد.</p>
        ) : (
          <ul className="max-h-32 space-y-1 overflow-y-auto rounded-xl border border-slate-200 bg-white p-2">
            {project.members.map((member: ProjectMember) => (
              <li key={member.user}>
                <label className="flex items-center gap-2 rounded-lg px-2 py-1 text-sm transition-colors hover:bg-slate-50">
                  <input type="checkbox" checked={assignees.includes(member.user)} onChange={() => toggle(member.user)} />
                  <span className="truncate">{member.user_name}</span>
                  <span className="truncate text-xs text-slate-500">{member.user_title}</span>
                </label>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="flex flex-wrap items-end gap-2">
        <div>
          <label className="mb-1 block text-xs text-slate-600" htmlFor="new-objective-due">
            مهلت
          </label>
          <JalaliDatePicker id="new-objective-due" value={dueOn} onChange={(iso) => setDueOn(iso ?? "")} required />
        </div>
        <div className="w-20">
          <label className="mb-1 block text-xs text-slate-600" htmlFor="new-objective-weight">
            وزن
          </label>
          <input
            id="new-objective-weight"
            aria-describedby="new-objective-weight-hint"
            type="number"
            min={1}
            max={100}
            value={weight}
            onChange={(e) => setWeight(Number(e.target.value) || 1)}
            className={input}
          />
        </div>
      </div>
      <p id="new-objective-weight-hint" className="text-xs text-slate-500">
        وزن: سهم این ریز هدف در درصد پیشرفت پروژه (۱ تا ۱۰۰). اگر همه ۱ بمانند، همه هم‌ارزش‌اند.
      </p>
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancel} className={buttonClass({ variant: "secondary", size: "sm" })}>
          انصراف
        </button>
        <button type="submit" disabled={saving} className={buttonClass({ variant: "primary", size: "sm" })}>
          {saving ? "در حال افزودن..." : "افزودن"}
        </button>
      </div>
    </form>
  );
}
