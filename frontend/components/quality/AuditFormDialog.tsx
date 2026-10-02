"use client";

import { useMemo, useState } from "react";
import { ApiError, apiPatch, apiPost } from "@/lib/api-client";
import { todayIso } from "@/lib/jalali";
import { nodeOptions, type OrgTreeResponse, type Person } from "@/lib/organization";
import {
  TITLE_MAX,
  auditCreatePayload,
  auditFormFrom,
  auditPatchPayload,
  emptyAuditForm,
  validateAuditForm,
  type AuditForm,
  type InternalAudit,
} from "@/lib/quality";
import { useApiQuery } from "@/lib/use-api-query";
import { JalaliDatePicker } from "@/components/JalaliDatePicker";
import { PersonPicker } from "@/components/PersonPicker";
import { ErrorBanner } from "@/components/StatusBanner";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogFooter } from "@/components/ui/Dialog";
import { Field, inputClass, selectClass } from "@/components/ui/Field";

/**
 * Plan an audit — or, with `audit`, change its plan (only while it is still «برنامه‌ریزی‌شده»: once it
 * runs, findings hang off its scope and date). Needs `manage_quality`; the page offers it only to
 * someone who has it. The scope is any active node of the chart (the audit covers it and everything
 * beneath); the date is today or later, checked only when new or changed so a late audit stays editable.
 * An edit sends only what changed.
 */
export function AuditFormDialog({
  audit,
  onSaved,
  onClose,
}: {
  audit?: InternalAudit;
  onSaved: (saved: InternalAudit) => void;
  onClose: () => void;
}) {
  const today = useMemo(() => todayIso(), []);
  const tree = useApiQuery<OrgTreeResponse>("/org/tree/");
  const [form, setForm] = useState<AuditForm>(() => (audit ? auditFormFrom(audit) : emptyAuditForm()));
  const [auditorName, setAuditorName] = useState<string | null>(audit?.lead_auditor_name ?? null);
  const [touched, setTouched] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const errors = validateAuditForm(form, today, audit);
  const shown = (key: keyof AuditForm) => (touched ? errors[key] : undefined);
  const set = (patch: Partial<AuditForm>) => setForm((current) => ({ ...current, ...patch }));
  const options = nodeOptions(tree.data?.nodes ?? []);
  // The current scope may have been archived since: keep it selectable-as-is rather than showing a blank.
  const scopeMissing = audit && !options.some((option) => option.id === audit.scope_node);

  function pick(person: Person) {
    set({ lead_auditor: person.id });
    setAuditorName(person.full_name);
  }

  async function submit() {
    setTouched(true);
    if (Object.keys(errors).length > 0) return;
    setSending(true);
    setError(null);
    try {
      if (audit) {
        const body = auditPatchPayload(audit, form);
        if (Object.keys(body).length === 0) {
          onClose();
          return;
        }
        onSaved(await apiPatch<InternalAudit>(`/quality/audits/${audit.id}/`, body));
      } else {
        onSaved(await apiPost<InternalAudit>("/quality/audits/", auditCreatePayload(form)));
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ذخیره ممکن نشد. دوباره تلاش کنید.");
      setSending(false);
    }
  }

  return (
    <Dialog
      label={audit ? "ویرایش ممیزی" : "برنامه‌ریزی ممیزی"}
      title={audit ? `ویرایش ${audit.code}` : "برنامه‌ریزی ممیزی داخلی"}
      description={
        audit ? undefined : "گرهٔ ممیزی‌شونده و همهٔ زیرمجموعه‌های آن بررسی می‌شوند. ممیز اصلی و مسئول آن گره از برنامه باخبر می‌شوند."
      }
      onClose={onClose}
      busy={sending}
      size="lg"
    >
      <Field label="عنوان" htmlFor="audit-title" required error={shown("title")}>
        <input
          id="audit-title"
          value={form.title}
          maxLength={TITLE_MAX}
          onChange={(e) => set({ title: e.target.value })}
          className={inputClass}
          autoFocus
        />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="گرهٔ ممیزی‌شونده" htmlFor="audit-scope" required error={shown("scope_node")}>
          <select
            id="audit-scope"
            value={form.scope_node ?? ""}
            onChange={(e) => set({ scope_node: e.target.value ? Number(e.target.value) : null })}
            className={`${selectClass} w-full`}
            disabled={tree.loading}
          >
            <option value="">{tree.loading ? "در حال بارگذاری..." : "انتخاب کنید"}</option>
            {scopeMissing && audit && <option value={audit.scope_node}>{audit.scope_node_name} (بایگانی‌شده)</option>}
            {options.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="تاریخ برنامه" htmlFor="audit-planned" required error={shown("planned_on")}>
          <JalaliDatePicker id="audit-planned" value={form.planned_on} onChange={(iso) => set({ planned_on: iso ?? "" })} min={today} required />
        </Field>
      </div>

      <div>
        <p className="mb-1.5 text-sm text-slate-700">
          ممیز اصلی <span aria-hidden className="text-rose-600">*</span>
        </p>
        {form.lead_auditor !== null && auditorName ? (
          <p className="flex items-center gap-2 rounded-xl bg-brand-50 px-3 py-2 text-sm text-brand-900">
            <Avatar name={auditorName} size="sm" />
            {auditorName}
            <button type="button" onClick={() => set({ lead_auditor: null })} className="ms-auto text-xs underline">
              تغییر
            </button>
          </p>
        ) : (
          <PersonPicker id="audit-auditor" ariaLabel="جست‌وجوی ممیز اصلی" pickLabel="انتخاب" onPick={pick} />
        )}
        {shown("lead_auditor") && (
          <p role="alert" className="mt-1.5 text-xs text-rose-700">
            {shown("lead_auditor")}
          </p>
        )}
      </div>

      {error && <ErrorBanner message={error} />}
      <DialogFooter>
        <Button onClick={onClose} disabled={sending}>
          انصراف
        </Button>
        <Button variant="primary" onClick={submit} loading={sending}>
          {audit ? "ذخیره" : "برنامه‌ریزی ممیزی"}
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
