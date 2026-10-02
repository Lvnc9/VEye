"use client";

import { useMemo, useState } from "react";
import { ApiError, apiPost } from "@/lib/api-client";
import { todayIso } from "@/lib/jalali";
import { nodeOptions, type OrgTreeResponse } from "@/lib/organization";
import {
  NC_SEVERITY_LABELS,
  TEXT_MAX,
  TITLE_MAX,
  emptyFindingForm,
  findingPayload,
  nodesWithin,
  validateFindingForm,
  type FindingForm,
  type InternalAudit,
  type NcSeverity,
  type NonConformance,
} from "@/lib/quality";
import { useApiQuery } from "@/lib/use-api-query";
import { JalaliDatePicker } from "@/components/JalaliDatePicker";
import { ErrorBanner } from "@/components/StatusBanner";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogFooter } from "@/components/ui/Dialog";
import { Field, inputClass, selectClass, textareaClass } from "@/components/ui/Field";

/**
 * Record a finding of a running audit. A finding *is* a non-conformance (the server files one with source
 * «ممیزی» and links it to the audit), so it then lives in the ordinary list and goes through triage
 * like any other. Its node is the audited node or any node beneath it — the picker offers nothing else,
 * and the server refuses anything else. An observation is simply «جزئی».
 */
export function FindingFormDialog({
  audit,
  onSaved,
  onClose,
}: {
  audit: InternalAudit;
  onSaved: (saved: NonConformance) => void;
  onClose: () => void;
}) {
  const today = useMemo(() => todayIso(), []);
  const tree = useApiQuery<OrgTreeResponse>("/org/tree/");
  const [form, setForm] = useState<FindingForm>(() => emptyFindingForm(audit.scope_node, today));
  const [touched, setTouched] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const errors = validateFindingForm(form, today);
  const shown = (key: keyof FindingForm) => (touched ? errors[key] : undefined);
  const set = (patch: Partial<FindingForm>) => setForm((current) => ({ ...current, ...patch }));
  const options = nodeOptions(nodesWithin(tree.data?.nodes ?? [], audit.scope_node));

  async function submit() {
    setTouched(true);
    if (Object.keys(errors).length > 0) return;
    setSending(true);
    setError(null);
    try {
      onSaved(await apiPost<NonConformance>(`/quality/audits/${audit.id}/findings/`, findingPayload(form)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ثبت یافته ممکن نشد. دوباره تلاش کنید.");
      setSending(false);
    }
  }

  return (
    <Dialog
      label="ثبت یافتهٔ ممیزی"
      title={`ثبت یافته در ${audit.code}`}
      description="آنچه در این ممیزی دیدید را بنویسید. یافته به‌عنوان یک عدم‌انطباق ثبت می‌شود و مسئول آن گره آن را بررسی می‌کند."
      onClose={onClose}
      busy={sending}
      size="lg"
    >
      <Field label="عنوان یافته" htmlFor="finding-title" required error={shown("title")}>
        <input
          id="finding-title"
          value={form.title}
          maxLength={TITLE_MAX}
          onChange={(e) => set({ title: e.target.value })}
          className={inputClass}
          autoFocus
        />
      </Field>
      <Field label="شرح" htmlFor="finding-description" required error={shown("description")}>
        <textarea
          id="finding-description"
          value={form.description}
          maxLength={TEXT_MAX}
          rows={4}
          onChange={(e) => set({ description: e.target.value })}
          className={textareaClass}
        />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="گرهٔ مربوط" htmlFor="finding-node" required error={shown("owner_node")} hint="خودِ گرهٔ ممیزی‌شونده یا یکی از زیرمجموعه‌های آن.">
          <select
            id="finding-node"
            value={form.owner_node ?? ""}
            onChange={(e) => set({ owner_node: e.target.value ? Number(e.target.value) : null })}
            className={`${selectClass} w-full`}
            disabled={tree.loading}
          >
            {tree.loading && <option value={audit.scope_node}>در حال بارگذاری...</option>}
            {options.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="شدت" htmlFor="finding-severity" hint="مشاهدهٔ ساده را «جزئی» بگذارید.">
          <select id="finding-severity" value={form.severity} onChange={(e) => set({ severity: e.target.value as NcSeverity })} className={`${selectClass} w-full`}>
            {(Object.keys(NC_SEVERITY_LABELS) as NcSeverity[]).map((value) => (
              <option key={value} value={value}>
                {NC_SEVERITY_LABELS[value]}
              </option>
            ))}
          </select>
        </Field>
        <Field label="تاریخ کشف" htmlFor="finding-detected" required error={shown("detected_on")}>
          <JalaliDatePicker id="finding-detected" value={form.detected_on} onChange={(iso) => set({ detected_on: iso ?? "" })} max={today} required />
        </Field>
      </div>

      {error && <ErrorBanner message={error} />}
      <DialogFooter>
        <Button onClick={onClose} disabled={sending}>
          انصراف
        </Button>
        <Button variant="primary" onClick={submit} loading={sending}>
          ثبت یافته
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
