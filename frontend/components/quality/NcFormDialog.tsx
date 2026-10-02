"use client";

import { useMemo, useState } from "react";
import { ApiError, apiPatch, apiPost } from "@/lib/api-client";
import { useCurrentUser } from "@/lib/current-user";
import { todayIso } from "@/lib/jalali";
import { nodeOptions, type OrgTreeResponse } from "@/lib/organization";
import {
  NC_SEVERITY_LABELS,
  NC_SOURCE_LABELS,
  TEXT_MAX,
  TITLE_MAX,
  createPayload,
  defaultOwnerNode,
  emptyForm,
  formFromNc,
  patchPayload,
  validateNcForm,
  type NcForm,
  type NcSeverity,
  type NcSource,
  type NonConformance,
} from "@/lib/quality";
import { useApiQuery } from "@/lib/use-api-query";
import { DocumentPicker } from "@/components/DocumentPicker";
import { JalaliDatePicker } from "@/components/JalaliDatePicker";
import { Code } from "@/components/Code";
import { ErrorBanner } from "@/components/StatusBanner";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogFooter } from "@/components/ui/Dialog";
import { Field, inputClass, selectClass, textareaClass } from "@/components/ui/Field";
import { X } from "lucide-react";

/**
 * Report a non-conformance — or, with `nc`, correct one. Anyone may report, against any active node:
 * the person who sees a problem in another unit is exactly who should say so, so the node picker lists
 * the whole chart, starting on the reporter's own home node. An edit sends only what changed.
 */
export function NcFormDialog({
  nc,
  onSaved,
  onClose,
}: {
  nc?: NonConformance;
  onSaved: (saved: NonConformance) => void;
  onClose: () => void;
}) {
  const { user } = useCurrentUser();
  const today = useMemo(() => todayIso(), []);
  const tree = useApiQuery<OrgTreeResponse>("/org/tree/");
  const [form, setForm] = useState<NcForm>(() => (nc ? formFromNc(nc) : emptyForm(defaultOwnerNode(user?.memberships), today)));
  const [documentLabel, setDocumentLabel] = useState<string | null>(
    nc?.related_document_code ? `${nc.related_document_code} — ${nc.related_document_title ?? ""}` : null,
  );
  const [touched, setTouched] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const errors = validateNcForm(form, today);
  const options = nodeOptions(tree.data?.nodes ?? []);
  const shown = (key: keyof NcForm) => (touched ? errors[key] : undefined);
  const set = (patch: Partial<NcForm>) => setForm((current) => ({ ...current, ...patch }));

  async function submit() {
    setTouched(true);
    if (Object.keys(errors).length > 0) return;
    setSending(true);
    setError(null);
    try {
      if (nc) {
        const body = patchPayload(nc, form);
        if (Object.keys(body).length === 0) {
          onClose();
          return;
        }
        onSaved(await apiPatch<NonConformance>(`/quality/nonconformances/${nc.id}/`, body));
      } else {
        onSaved(await apiPost<NonConformance>("/quality/nonconformances/", createPayload(form)));
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ذخیره ممکن نشد. دوباره تلاش کنید.");
      setSending(false);
    }
  }

  return (
    <Dialog
      label={nc ? "ویرایش عدم‌انطباق" : "ثبت عدم‌انطباق"}
      title={nc ? `ویرایش ${nc.code}` : "ثبت عدم‌انطباق"}
      description={
        nc
          ? undefined
          : "مشکلی که دیده‌اید را بنویسید. مسئول آن بخش آن را بررسی می‌کند و در صورت پذیرش، اقدام اصلاحی تعیین می‌شود."
      }
      onClose={onClose}
      busy={sending}
      size="lg"
    >
      <Field label="عنوان" htmlFor="nc-title" required error={shown("title")}>
        <input
          id="nc-title"
          value={form.title}
          maxLength={TITLE_MAX}
          onChange={(e) => set({ title: e.target.value })}
          className={inputClass}
          autoFocus
        />
      </Field>
      <Field label="شرح مشکل" htmlFor="nc-description" required error={shown("description")}>
        <textarea
          id="nc-description"
          value={form.description}
          maxLength={TEXT_MAX}
          rows={4}
          onChange={(e) => set({ description: e.target.value })}
          className={textareaClass}
        />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="منبع" htmlFor="nc-source">
          <select id="nc-source" value={form.source} onChange={(e) => set({ source: e.target.value as NcSource })} className={`${selectClass} w-full`}>
            {(Object.keys(NC_SOURCE_LABELS) as NcSource[]).map((value) => (
              <option key={value} value={value}>
                {NC_SOURCE_LABELS[value]}
              </option>
            ))}
          </select>
        </Field>
        <Field label="شدت" htmlFor="nc-severity">
          <select id="nc-severity" value={form.severity} onChange={(e) => set({ severity: e.target.value as NcSeverity })} className={`${selectClass} w-full`}>
            {(Object.keys(NC_SEVERITY_LABELS) as NcSeverity[]).map((value) => (
              <option key={value} value={value}>
                {NC_SEVERITY_LABELS[value]}
              </option>
            ))}
          </select>
        </Field>
        <Field label="گرهٔ مربوط" htmlFor="nc-node" required error={shown("owner_node")} hint="بخشی که مشکل به فرایند آن مربوط است — لازم نیست عضو آن باشید.">
          <select
            id="nc-node"
            value={form.owner_node ?? ""}
            onChange={(e) => set({ owner_node: e.target.value ? Number(e.target.value) : null })}
            className={`${selectClass} w-full`}
            disabled={tree.loading}
          >
            <option value="">{tree.loading ? "در حال بارگذاری..." : "انتخاب کنید"}</option>
            {options.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="تاریخ کشف" htmlFor="nc-detected" required error={shown("detected_on")}>
          <JalaliDatePicker id="nc-detected" value={form.detected_on} onChange={(iso) => set({ detected_on: iso ?? "" })} max={today} required />
        </Field>
      </div>

      {form.related_document !== null && documentLabel ? (
        <p className="flex items-center gap-2 rounded-xl bg-slate-50 px-3 py-2 text-sm ring-1 ring-inset ring-slate-200">
          <span className="text-slate-500">مستند مرتبط:</span>
          <Code>{documentLabel.split(" — ")[0]}</Code>
          <span className="min-w-0 truncate">{documentLabel.split(" — ").slice(1).join(" — ")}</span>
          <button
            type="button"
            aria-label="برداشتن مستند مرتبط"
            onClick={() => {
              set({ related_document: null });
              setDocumentLabel(null);
            }}
            className="ms-auto flex size-6 items-center justify-center rounded-full text-slate-500 hover:bg-slate-200 hover:text-slate-800"
          >
            <X className="size-4" />
          </button>
        </p>
      ) : (
        <DocumentPicker
          id="nc-document"
          label="مستند مرتبط (اختیاری) — روش اجرایی یا دستورالعملی که این مورد به آن مربوط است"
          pickLabel="انتخاب"
          doneLabel="انتخاب شد"
          onPick={(document) => {
            set({ related_document: document.id });
            setDocumentLabel(`${document.full_code} — ${document.title}`);
          }}
        />
      )}

      {error && <ErrorBanner message={error} />}
      <DialogFooter>
        <Button onClick={onClose} disabled={sending}>
          انصراف
        </Button>
        <Button variant="primary" onClick={submit} loading={sending}>
          {nc ? "ذخیره" : "ثبت عدم‌انطباق"}
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
