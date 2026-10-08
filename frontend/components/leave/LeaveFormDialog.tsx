"use client";

import { useState } from "react";
import { ApiError, apiPost } from "@/lib/api-client";
import {
  LEAVE_TYPE_LABELS,
  REASON_MAX,
  daysText,
  emptyLeaveForm,
  inclusiveDays,
  leavePayload,
  validateLeaveForm,
  type LeaveForm,
  type LeaveType,
} from "@/lib/leave";
import { JalaliDatePicker } from "@/components/JalaliDatePicker";
import { ErrorBanner } from "@/components/StatusBanner";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogFooter } from "@/components/ui/Dialog";
import { Field, selectClass, textareaClass } from "@/components/ui/Field";

/**
 * Ask for days off: the type, the first and last day (both included — a past day is allowed, sick leave is
 * usually recorded afterwards) and an optional note. The number of days is shown as the dates are picked.
 * The request goes to the مسئول of the unit you sit in (or above); the server refuses one that overlaps a
 * request of yours still pending or approved, and says so here.
 */
export function LeaveFormDialog({ onSaved, onClose }: { onSaved: () => void; onClose: () => void }) {
  const [form, setForm] = useState<LeaveForm>(emptyLeaveForm);
  const [touched, setTouched] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const errors = validateLeaveForm(form);
  const shown = (key: keyof LeaveForm) => (touched ? errors[key] : undefined);
  const set = (patch: Partial<LeaveForm>) => setForm((current) => ({ ...current, ...patch }));
  const days = inclusiveDays(form.starts_on, form.ends_on);

  async function submit() {
    setTouched(true);
    if (Object.keys(errors).length > 0) return;
    setSending(true);
    setError(null);
    try {
      await apiPost("/leave/requests/", leavePayload(form));
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ثبت درخواست ممکن نشد. دوباره تلاش کنید.");
      setSending(false);
    }
  }

  return (
    <Dialog
      label="درخواست مرخصی"
      title="درخواست مرخصی"
      description="درخواست برای مسئول واحد شما (یا بالادست او) فرستاده می‌شود و از نتیجه باخبر می‌شوید."
      onClose={onClose}
      busy={sending}
    >
      <Field label="نوع مرخصی" htmlFor="leave-type">
        <select id="leave-type" value={form.leave_type} onChange={(e) => set({ leave_type: e.target.value as LeaveType })} className={`${selectClass} w-full`}>
          {(Object.keys(LEAVE_TYPE_LABELS) as LeaveType[]).map((value) => (
            <option key={value} value={value}>
              {LEAVE_TYPE_LABELS[value]}
            </option>
          ))}
        </select>
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="از روز" htmlFor="leave-start" required error={shown("starts_on")}>
          <JalaliDatePicker
            id="leave-start"
            value={form.starts_on}
            onChange={(iso) => set({ starts_on: iso ?? "", ends_on: form.ends_on && iso && form.ends_on < iso ? iso : form.ends_on })}
            required
          />
        </Field>
        <Field label="تا روز" htmlFor="leave-end" required error={shown("ends_on")}>
          <JalaliDatePicker id="leave-end" value={form.ends_on} onChange={(iso) => set({ ends_on: iso ?? "" })} min={form.starts_on || undefined} required />
        </Field>
      </div>
      <p className="rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-700 ring-1 ring-inset ring-slate-200" aria-live="polite">
        {days === null ? "روز شروع و پایان را انتخاب کنید." : <>جمعاً <b>{daysText(days)}</b> (هر دو روز شروع و پایان شمرده می‌شود)</>}
      </p>
      <Field label="توضیح (اختیاری)" htmlFor="leave-reason" error={shown("reason")}>
        <textarea id="leave-reason" value={form.reason} maxLength={REASON_MAX} rows={3} onChange={(e) => set({ reason: e.target.value })} className={textareaClass} />
      </Field>
      {error && <ErrorBanner message={error} />}
      <DialogFooter>
        <Button onClick={onClose} disabled={sending}>
          انصراف
        </Button>
        <Button variant="primary" onClick={submit} loading={sending}>
          ثبت درخواست
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
