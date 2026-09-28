"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, apiPatch } from "@/lib/api-client";
import { editObjectiveBody, type Objective, type ProjectMember } from "@/lib/projects";
import { ErrorBanner } from "@/components/StatusBanner";
import { JalaliDatePicker } from "@/components/JalaliDatePicker";
import { buttonClass } from "@/components/ui/Button";
import { controlClass } from "@/components/ui/Field";
import { Dialog } from "@/components/ui/Dialog";

const input = `${controlClass} w-full px-3 py-2 text-sm`;
const label = "mb-1.5 block text-sm text-slate-700";

/** «ویرایش» on the objective card: everything `can_edit` covers except position, which is the
 *  ▲/▼ buttons' job. `assignees` always replaces the whole set (the API contract, not a diff). */
export function ObjectiveEditDialog({
  projectId,
  objective,
  members,
  onSaved,
  onCancel,
}: {
  projectId: number;
  objective: Objective;
  members: ProjectMember[];
  onSaved: () => void;
  onCancel: () => void;
}) {
  const firstField = useRef<HTMLInputElement>(null);
  const [title, setTitle] = useState(objective.title);
  const [description, setDescription] = useState(objective.description);
  const [assignees, setAssignees] = useState<number[]>(objective.assignees.map((a) => a.user));
  const [dueOn, setDueOn] = useState(objective.due_on);
  const [weight, setWeight] = useState(objective.weight);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    firstField.current?.focus();
  }, []);

  function toggle(user: number) {
    setAssignees((current) => (current.includes(user) ? current.filter((u) => u !== user) : [...current, user]));
  }

  async function submit() {
    if (!title.trim() || assignees.length === 0 || !dueOn) {
      setError("عنوان، دست‌کم یک مسئول و مهلت الزامی است.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await apiPatch(
        `/projects/${projectId}/objectives/${objective.id}/`,
        editObjectiveBody({ title, description, assignees, due_on: dueOn, weight }),
      );
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ویرایش ریزهدف ممکن نشد.");
      setSaving(false);
    }
  }

  return (
    <Dialog label={`ویرایش ${objective.title}`} title="ویرایش ریزهدف" onClose={onCancel} busy={saving}>
        {error && <ErrorBanner message={error} />}

        <div>
          <label className={label} htmlFor="edit-objective-title">
            عنوان
          </label>
          <input
            ref={firstField}
            id="edit-objective-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={255}
            className={input}
          />
        </div>

        <div>
          <label className={label} htmlFor="edit-objective-description">
            شرح
          </label>
          <textarea
            id="edit-objective-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className={input}
          />
        </div>

        <div>
          <span className={label}>مسئولان</span>
          {members.length === 0 ? (
            <p className="text-xs text-slate-500">این پروژه هنوز عضوی ندارد.</p>
          ) : (
            <ul className="max-h-40 space-y-1 overflow-y-auto rounded-lg border border-slate-200 p-2">
              {members.map((member) => (
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

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={label} htmlFor="edit-objective-due">
              مهلت
            </label>
            <JalaliDatePicker id="edit-objective-due" value={dueOn} onChange={(iso) => setDueOn(iso ?? "")} required />
          </div>
          <div>
            <label className={label} htmlFor="edit-objective-weight">
              وزن
            </label>
            <input
              id="edit-objective-weight"
              aria-describedby="edit-objective-weight-hint"
              type="number"
              min={1}
              max={100}
              value={weight}
              onChange={(e) => setWeight(Number(e.target.value) || 1)}
              className={input}
            />
          </div>
          <p id="edit-objective-weight-hint" className="col-span-2 -mt-2 text-xs text-slate-500">
            وزن: سهم این ریز هدف در درصد پیشرفت پروژه (۱ تا ۱۰۰). اگر همه ۱ بمانند، همه هم‌ارزش‌اند.
          </p>
        </div>

        <div className="flex justify-end gap-2 border-t border-slate-100 pt-4">
          <button
            type="button"
            onClick={onCancel}
            disabled={saving}
            className={buttonClass({ variant: "secondary", size: "md" })}
          >
            انصراف
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={saving}
            className={buttonClass({ variant: "primary", size: "md" })}
          >
            {saving ? "در حال ذخیره..." : "ذخیره"}
          </button>
        </div>
    </Dialog>
  );
}
