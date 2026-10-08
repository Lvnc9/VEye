"use client";

import { useMemo, useState } from "react";
import { ApiError, apiPatch, apiPost } from "@/lib/api-client";
import { useCurrentUser } from "@/lib/current-user";
import { toPersianDigits, todayIso } from "@/lib/jalali";
import { nodeOptions, type OrgTreeResponse, type Person } from "@/lib/organization";
import {
  IMPACT_LABELS,
  LIKELIHOOD_LABELS,
  RISK_LEVEL_LABELS,
  RISK_SCALE,
  RISK_STATUS_LABELS,
  TEXT_MAX,
  TITLE_MAX,
  assessmentText,
  emptyRiskForm,
  manageableNodes,
  riskCreatePayload,
  riskFormFrom,
  riskLevel,
  riskPatchPayload,
  validateRiskForm,
  type RiskForm,
  type RiskItem,
  type RiskStatus,
} from "@/lib/quality";
import { useApiQuery } from "@/lib/use-api-query";
import { JalaliDatePicker } from "@/components/JalaliDatePicker";
import { PersonPicker } from "@/components/PersonPicker";
import { RiskLevelBadge } from "@/components/quality/Badges";
import { ErrorBanner } from "@/components/StatusBanner";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogFooter } from "@/components/ui/Dialog";
import { Field, inputClass, selectClass, textareaClass } from "@/components/ui/Field";

/**
 * Record a risk — or, with `risk`, change one (its status too: the register is permissive, every change
 * is recorded). Offered only to someone the server lets do it: `manage_quality`, or a lead of the node or
 * one above it — so the node picker lists exactly those nodes. Likelihood and impact are picked from
 * labelled 1-5 scales with the score and level shown as they change (the same bands as the server). An
 * edit sends only what changed.
 */
export function RiskFormDialog({
  risk,
  onSaved,
  onClose,
}: {
  risk?: RiskItem;
  onSaved: (saved: RiskItem) => void;
  onClose: () => void;
}) {
  const { user, can } = useCurrentUser();
  const today = useMemo(() => todayIso(), []);
  const tree = useApiQuery<OrgTreeResponse>("/org/tree/");
  const allowed = manageableNodes(tree.data?.nodes ?? [], user?.memberships, can("manage_quality"));
  const firstLed = user?.memberships?.find((m) => m.is_lead)?.node ?? null;
  const [form, setForm] = useState<RiskForm>(() => (risk ? riskFormFrom(risk) : emptyRiskForm(firstLed)));
  const [ownerName, setOwnerName] = useState<string | null>(risk?.owner_name ?? null);
  const [touched, setTouched] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const errors = validateRiskForm(form, today, risk);
  const shown = (key: keyof RiskForm) => (touched ? errors[key] : undefined);
  const set = (patch: Partial<RiskForm>) => setForm((current) => ({ ...current, ...patch }));
  const options = nodeOptions(allowed);
  // Editing a risk whose node the editor manages from above, or one since archived: keep it selectable.
  const nodeMissing = risk && !options.some((option) => option.id === risk.owner_node);
  const level = riskLevel(form.likelihood * form.impact);

  function pickOwner(person: Person) {
    set({ owner: person.id });
    setOwnerName(person.full_name);
  }

  async function submit() {
    setTouched(true);
    if (Object.keys(errors).length > 0) return;
    setSending(true);
    setError(null);
    try {
      if (risk) {
        const body = riskPatchPayload(risk, form);
        if (Object.keys(body).length === 0) {
          onClose();
          return;
        }
        onSaved(await apiPatch<RiskItem>(`/quality/risks/${risk.id}/`, body));
      } else {
        onSaved(await apiPost<RiskItem>("/quality/risks/", riskCreatePayload(form)));
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ذخیره ممکن نشد. دوباره تلاش کنید.");
      setSending(false);
    }
  }

  return (
    <Dialog
      label={risk ? "ویرایش ریسک" : "ثبت ریسک"}
      title={risk ? `ویرایش ${risk.code}` : "ثبت ریسک"}
      description={risk ? undefined : "مشکلی که هنوز رخ نداده اما ممکن است رخ دهد: چقدر محتمل است، اگر رخ دهد چقدر اثر دارد و چه کاری برای آن می‌شود."}
      onClose={onClose}
      busy={sending}
      size="lg"
    >
      <Field label="عنوان" htmlFor="risk-title" required error={shown("title")}>
        <input id="risk-title" value={form.title} maxLength={TITLE_MAX} onChange={(e) => set({ title: e.target.value })} className={inputClass} autoFocus />
      </Field>
      <Field label="شرح" htmlFor="risk-description" required error={shown("description")}>
        <textarea
          id="risk-description"
          value={form.description}
          maxLength={TEXT_MAX}
          rows={3}
          onChange={(e) => set({ description: e.target.value })}
          className={textareaClass}
        />
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="احتمال" htmlFor="risk-likelihood" required error={shown("likelihood")}>
          <select id="risk-likelihood" value={form.likelihood} onChange={(e) => set({ likelihood: Number(e.target.value) })} className={`${selectClass} w-full`}>
            {RISK_SCALE.map((value) => (
              <option key={value} value={value}>
                {`${toPersianDigits(value)} — ${LIKELIHOOD_LABELS[value]}`}
              </option>
            ))}
          </select>
        </Field>
        <Field label="اثر" htmlFor="risk-impact" required error={shown("impact")}>
          <select id="risk-impact" value={form.impact} onChange={(e) => set({ impact: Number(e.target.value) })} className={`${selectClass} w-full`}>
            {RISK_SCALE.map((value) => (
              <option key={value} value={value}>
                {`${toPersianDigits(value)} — ${IMPACT_LABELS[value]}`}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <p className="flex flex-wrap items-center gap-2 rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-700 ring-1 ring-inset ring-slate-200" aria-live="polite">
        امتیاز ریسک:
        <span className="font-bold">{assessmentText(form.likelihood, form.impact)}</span>
        <RiskLevelBadge level={level} label={RISK_LEVEL_LABELS[level]} />
      </p>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="گرهٔ مربوط" htmlFor="risk-node" required error={shown("owner_node")} hint="بخشی که این ریسک به فرایند آن مربوط است.">
          <select
            id="risk-node"
            value={form.owner_node ?? ""}
            onChange={(e) => set({ owner_node: e.target.value ? Number(e.target.value) : null })}
            className={`${selectClass} w-full`}
            disabled={tree.loading}
          >
            <option value="">{tree.loading ? "در حال بارگذاری..." : "انتخاب کنید"}</option>
            {nodeMissing && risk && <option value={risk.owner_node}>{risk.owner_node_name}</option>}
            {options.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="تاریخ بازنگری (اختیاری)" htmlFor="risk-review" error={shown("review_on")}>
          <JalaliDatePicker id="risk-review" value={form.review_on} onChange={(iso) => set({ review_on: iso ?? "" })} min={today} />
        </Field>
        {risk && (
          <Field label="وضعیت" htmlFor="risk-status">
            <select id="risk-status" value={form.status} onChange={(e) => set({ status: e.target.value as RiskStatus })} className={`${selectClass} w-full`}>
              {(Object.keys(RISK_STATUS_LABELS) as RiskStatus[]).map((value) => (
                <option key={value} value={value}>
                  {RISK_STATUS_LABELS[value]}
                </option>
              ))}
            </select>
          </Field>
        )}
      </div>

      <div>
        <p className="mb-1.5 text-sm text-slate-700">مسئول پیگیری (اختیاری)</p>
        {form.owner !== null && ownerName ? (
          <p className="flex items-center gap-2 rounded-xl bg-brand-50 px-3 py-2 text-sm text-brand-900">
            <Avatar name={ownerName} size="sm" />
            {ownerName}
            <button type="button" onClick={() => set({ owner: null })} className="ms-auto text-xs underline">
              برداشتن
            </button>
          </p>
        ) : (
          <PersonPicker id="risk-owner" ariaLabel="جست‌وجوی مسئول پیگیری" pickLabel="انتخاب" onPick={pickOwner} />
        )}
      </div>

      <Field label="برنامهٔ کاهش (اختیاری)" htmlFor="risk-plan" error={shown("mitigation_plan")}>
        <textarea
          id="risk-plan"
          value={form.mitigation_plan}
          maxLength={TEXT_MAX}
          rows={3}
          onChange={(e) => set({ mitigation_plan: e.target.value })}
          className={textareaClass}
        />
      </Field>

      {error && <ErrorBanner message={error} />}
      <DialogFooter>
        <Button onClick={onClose} disabled={sending}>
          انصراف
        </Button>
        <Button variant="primary" onClick={submit} loading={sending}>
          {risk ? "ذخیره" : "ثبت ریسک"}
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
