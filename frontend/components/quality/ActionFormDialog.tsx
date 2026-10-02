"use client";

import { useMemo, useState } from "react";
import { ApiError, apiPatch, apiPost } from "@/lib/api-client";
import { todayIso } from "@/lib/jalali";
import type { Person } from "@/lib/organization";
import {
  TEXT_MAX,
  TITLE_MAX,
  actionCreatePayload,
  actionFormFrom,
  actionPatchPayload,
  emptyActionForm,
  validateActionForm,
  type ActionForm,
  type CorrectiveAction,
} from "@/lib/quality";
import { JalaliDatePicker } from "@/components/JalaliDatePicker";
import { PersonPicker } from "@/components/PersonPicker";
import { ErrorBanner } from "@/components/StatusBanner";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogFooter } from "@/components/ui/Dialog";
import { Field, inputClass, textareaClass } from "@/components/ui/Field";

/**
 * Add a corrective action — or, with `action`, change one. One named assignee (the person accountable),
 * a required deadline (today or later; an overdue action keeps its old date unless someone re-dates it)
 * and what is to be done. An edit sends only what changed.
 */
export function ActionFormDialog({
  ncId,
  action,
  onSaved,
  onClose,
}: {
  ncId: number;
  action?: CorrectiveAction;
  onSaved: () => void;
  onClose: () => void;
}) {
  const today = useMemo(() => todayIso(), []);
  const [form, setForm] = useState<ActionForm>(() => (action ? actionFormFrom(action) : emptyActionForm()));
  const [assigneeName, setAssigneeName] = useState<string | null>(action?.assignee_name ?? null);
  const [touched, setTouched] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const errors = validateActionForm(form, today, action);
  const shown = (key: keyof ActionForm) => (touched ? errors[key] : undefined);
  const set = (patch: Partial<ActionForm>) => setForm((current) => ({ ...current, ...patch }));
  const pick = (person: Person) => {
    set({ assignee: person.id });
    setAssigneeName(person.full_name);
  };

  async function submit() {
    setTouched(true);
    if (Object.keys(errors).length > 0) return;
    setSending(true);
    setError(null);
    try {
      if (action) {
        const body = actionPatchPayload(action, form);
        if (Object.keys(body).length === 0) {
          onClose();
          return;
        }
        await apiPatch(`/quality/nonconformances/${ncId}/actions/${action.id}/`, body);
      } else {
        await apiPost(`/quality/nonconformances/${ncId}/actions/`, actionCreatePayload(form));
      }
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ذخیره ممکن نشد. دوباره تلاش کنید.");
      setSending(false);
    }
  }

  return (
    <Dialog
      label={action ? "ویرایش اقدام اصلاحی" : "افزودن اقدام اصلاحی"}
      title={action ? "ویرایش اقدام اصلاحی" : "افزودن اقدام اصلاحی"}
      description={action ? undefined : "چه کاری، توسط چه کسی و تا چه زمانی انجام شود تا مشکل برطرف شود؟"}
      onClose={onClose}
      busy={sending}
      size="lg"
    >
      <Field label="عنوان اقدام" htmlFor="action-title" required error={shown("title")}>
        <input
          id="action-title"
          value={form.title}
          maxLength={TITLE_MAX}
          onChange={(e) => set({ title: e.target.value })}
          className={inputClass}
          autoFocus
        />
      </Field>
      <Field label="شرح (اختیاری)" htmlFor="action-description" error={shown("description")}>
        <textarea
          id="action-description"
          value={form.description}
          maxLength={TEXT_MAX}
          rows={3}
          onChange={(e) => set({ description: e.target.value })}
          className={textareaClass}
        />
      </Field>

      <div>
        <p className="mb-1.5 text-sm text-slate-700">
          مسئول انجام <span aria-hidden className="text-rose-600">*</span>
        </p>
        {form.assignee !== null && assigneeName ? (
          <p className="flex items-center gap-2 rounded-xl bg-brand-50 px-3 py-2 text-sm text-brand-900">
            <Avatar name={assigneeName} size="sm" />
            {assigneeName}
            <button type="button" onClick={() => set({ assignee: null })} className="ms-auto text-xs underline">
              تغییر
            </button>
          </p>
        ) : (
          <PersonPicker id="action-assignee" ariaLabel="جست‌وجوی مسئول انجام" pickLabel="انتخاب" onPick={pick} />
        )}
        {shown("assignee") && (
          <p role="alert" className="mt-1.5 text-xs text-rose-700">
            {shown("assignee")}
          </p>
        )}
      </div>

      <Field label="مهلت" htmlFor="action-due" required error={shown("due_on")}>
        <JalaliDatePicker id="action-due" value={form.due_on} onChange={(iso) => set({ due_on: iso ?? "" })} min={today} required />
      </Field>

      {error && <ErrorBanner message={error} />}
      <DialogFooter>
        <Button onClick={onClose} disabled={sending}>
          انصراف
        </Button>
        <Button variant="primary" onClick={submit} loading={sending}>
          {action ? "ذخیره" : "افزودن اقدام"}
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
