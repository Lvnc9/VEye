"use client";

import { useEffect, useState } from "react";
import { ApiError, apiGet, apiPost } from "@/lib/api-client";
import { formatJalali, toPersianDigits } from "@/lib/jalali";
import {
  LEAVE_TYPE_LABELS,
  REASON_MAX,
  emptyLeaveForm,
  leavePayload,
  validateLeaveForm,
  workingDaysText,
  type LeaveForm,
  type LeavePreview,
  type LeaveType,
} from "@/lib/leave";
import { Alert } from "@/components/ui/Alert";
import { JalaliDatePicker } from "@/components/JalaliDatePicker";
import { ErrorBanner } from "@/components/StatusBanner";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogFooter } from "@/components/ui/Dialog";
import { Field, selectClass, textareaClass } from "@/components/ui/Field";

/**
 * Ask for days off: the type, the first and last day (both included — a past day is allowed, sick leave is
 * usually recorded afterwards) and an optional note. The working days (Phase 22: Fridays and holidays are free) and,
 * for annual leave, what would be left are asked of the server as the dates are picked.
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
  const preview = useLeavePreview(form);

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
      <div className="space-y-1 rounded-xl bg-muted/50 px-3 py-2 text-sm text-soft-foreground ring-1 ring-inset ring-border" aria-live="polite">
        {!preview ? (
          <p>روز شروع و پایان را انتخاب کنید.</p>
        ) : (
          <>
            <p>
              جمعاً <b>{workingDaysText(preview.days, preview.calendar_days)}</b> — جمعه‌ها و تعطیلات رسمی شمرده نمی‌شوند.
            </p>
            {preview.holidays.length > 0 && (
              <p className="text-xs text-muted-foreground">
                تعطیلات این بازه: {preview.holidays.map((h) => `${h.title} (${formatJalali(h.date)})`).join("، ")}
              </p>
            )}
            {preview.balance.map((b) =>
              b.exceeds ? null : (
                <p key={b.year} className="text-xs text-muted-foreground">
                  ماندهٔ مرخصی استحقاقی شما در {toPersianDigits(b.year)} پس از این درخواست:{" "}
                  {toPersianDigits(b.remaining - b.requested)} روز
                </p>
              ),
            )}
          </>
        )}
      </div>
      {preview?.balance
        .filter((b) => b.exceeds)
        .map((b) => (
          <Alert key={b.year} tone="warning">
            این درخواست بیش از ماندهٔ مرخصی استحقاقی شماست ({toPersianDigits(b.requested)} روز درخواست،{" "}
            {toPersianDigits(Math.max(b.remaining, 0))} روز مانده در {toPersianDigits(b.year)}). می‌توانید ثبت کنید؛ تصمیم با
            مسئول شماست.
          </Alert>
        ))}
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


/** The server's count for the picked span (`/leave/requests/preview/`); null while the dates are incomplete. */
function useLeavePreview(form: LeaveForm): LeavePreview | null {
  const ready = Boolean(form.starts_on && form.ends_on && form.ends_on >= form.starts_on);
  const key = ready ? `${form.starts_on}|${form.ends_on}|${form.leave_type}` : "";
  const [loaded, setLoaded] = useState<{ key: string; preview: LeavePreview } | null>(null);
  useEffect(() => {
    if (!key) return;
    let cancelled = false;
    const [starts_on, ends_on, leave_type] = key.split("|");
    apiGet<LeavePreview>("/leave/requests/preview/", { starts_on, ends_on, leave_type })
      .then((preview) => !cancelled && setLoaded({ key, preview }))
      .catch(() => {
        // The count is a help, not a gate: the server checks the request itself when it is sent.
      });
    return () => {
      cancelled = true;
    };
  }, [key]);
  return key && loaded?.key === key ? loaded.preview : null;
}
