"use client";

import { useState, type FormEvent } from "react";
import { ApiError, apiDelete, apiPatch, apiPost } from "@/lib/api-client";
import { formatJalali } from "@/lib/jalali";
import {
  OBJECTIVE_STATUS_LABELS,
  OBJECTIVE_STATUS_TONE,
  type Objective,
  type ObjectiveStatus,
  type ProjectDetail,
  type ProjectMember,
} from "@/lib/projects";
import { ErrorBanner } from "@/components/StatusBanner";

const select = "rounded border border-slate-300 bg-white px-2 py-1 text-xs";
const input = "w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm";

/** «اهداف» (docs/11 §3.5): title, assignee, Jalali deadline, a status select, an overdue tint.
 *  Reordering is two plain buttons, not drag-and-drop — no new frontend dependency. */
export function ObjectivesList({
  project,
  objectives,
  onChanged,
}: {
  project: ProjectDetail;
  objectives: Objective[];
  onChanged: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);

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
    <section aria-label="اهداف" className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-900">اهداف</h2>
        {project.can_edit && (
          <button type="button" onClick={() => setAdding((v) => !v)} className="text-sm text-slate-700 underline hover:text-slate-900">
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
      {objectives.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500">هنوز ریزهدفی افزوده نشده است.</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {objectives.map((objective, index) => (
            <li
              key={objective.id}
              className={`rounded-lg border p-3 ${objective.is_overdue ? "border-red-200 bg-red-50" : "border-slate-100"}`}
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-medium text-slate-900">{objective.title}</p>
                  {objective.description && <p className="mt-0.5 text-xs text-slate-600">{objective.description}</p>}
                  <p className="mt-1 text-xs text-slate-500">
                    {objective.assignee_name} · مهلت: {formatJalali(objective.due_on)}
                    {objective.is_overdue && <span className="mr-1 font-medium text-red-700">(دیرکرد)</span>}
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
                        className="leading-none text-slate-400 hover:text-slate-800 disabled:opacity-30"
                      >
                        ▲
                      </button>
                      <button
                        type="button"
                        aria-label="جابه‌جایی به پایین"
                        disabled={index === objectives.length - 1}
                        onClick={() => move(index, 1)}
                        className="leading-none text-slate-400 hover:text-slate-800 disabled:opacity-30"
                      >
                        ▼
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
                    <RemoveObjectiveButton
                      project={project}
                      objective={objective}
                      onRemoved={onChanged}
                      onError={setError}
                    />
                  )}
                </div>
              </div>
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
      className="rounded px-1.5 text-xs text-red-600 hover:bg-red-50 disabled:opacity-50"
    >
      حذف
    </button>
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
  const [assignee, setAssignee] = useState<number | "">("");
  const [dueOn, setDueOn] = useState("");
  const [weight, setWeight] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim() || !assignee || !dueOn) {
      setError("عنوان، مسئول و مهلت الزامی است.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await apiPost(`/projects/${project.id}/objectives/`, { title: title.trim(), assignee, due_on: dueOn, weight });
      onAdded();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "افزودن ریزهدف ممکن نشد.");
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="mb-3 space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
      {error && <ErrorBanner message={error} />}
      <div className="flex flex-wrap items-end gap-2">
        <div className="flex-1">
          <label className="mb-1 block text-xs text-slate-600" htmlFor="new-objective-title">
            عنوان
          </label>
          <input id="new-objective-title" value={title} onChange={(e) => setTitle(e.target.value)} className={input} />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-600" htmlFor="new-objective-assignee">
            مسئول
          </label>
          <select
            id="new-objective-assignee"
            value={assignee}
            onChange={(e) => setAssignee(e.target.value ? Number(e.target.value) : "")}
            className={input}
          >
            <option value="">انتخاب کنید…</option>
            {project.members.map((member: ProjectMember) => (
              <option key={member.user} value={member.user}>
                {member.user_name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-600" htmlFor="new-objective-due">
            مهلت
          </label>
          <input id="new-objective-due" type="date" value={dueOn} onChange={(e) => setDueOn(e.target.value)} className={input} />
        </div>
        <div className="w-20">
          <label className="mb-1 block text-xs text-slate-600" htmlFor="new-objective-weight">
            وزن
          </label>
          <input
            id="new-objective-weight"
            type="number"
            min={1}
            max={100}
            value={weight}
            onChange={(e) => setWeight(Number(e.target.value) || 1)}
            className={input}
          />
        </div>
      </div>
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancel} className="rounded border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50">
          انصراف
        </button>
        <button type="submit" disabled={saving} className="rounded bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-700 disabled:opacity-50">
          {saving ? "در حال افزودن..." : "افزودن"}
        </button>
      </div>
    </form>
  );
}
