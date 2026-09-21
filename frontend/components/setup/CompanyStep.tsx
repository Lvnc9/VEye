"use client";

import { useState, type FormEvent } from "react";
import { ApiError, apiDelete, apiPatch, apiUpload } from "@/lib/api-client";
import type { Company, OrgNode } from "@/lib/organization";
import { AddNodeForm, DeleteNodeButton } from "./AddNodeForm";
import { DarkError, StepCard, darkInput, ghostButton, primaryButton } from "./ui";

/**
 * Step 1: the company's name and logo, and whether it has several حوزه.
 *
 * «آیا شرکت چند حوزه دارد؟» is a real choice, not a flag on the model: a company with no حوزه simply
 * puts its واحد straight under the company node, and the chart is exactly as valid.
 */
export function CompanyStep({
  company,
  nodes,
  onChanged,
  onNext,
}: {
  company: Company;
  nodes: OrgNode[];
  onChanged: () => void;
  onNext: () => void;
}) {
  const domains = nodes.filter((node) => node.kind === "DOMAIN");
  const [name, setName] = useState(company.name);
  const [multi, setMulti] = useState<boolean | null>(domains.length > 0 ? true : null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function run(action: () => Promise<unknown>, fallback: string) {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      await action();
      onChanged();
      return true;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : fallback);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function saveName(event: FormEvent) {
    event.preventDefault();
    if (!name.trim() || name.trim() === company.name) return;
    if (await run(() => apiPatch("/org/company/", { name: name.trim() }), "ذخیرهٔ نام ممکن نشد.")) setSaved(true);
  }

  async function uploadLogo(file: File | undefined) {
    if (!file) return;
    const body = new FormData();
    body.append("logo", file);
    await run(() => apiUpload("/org/company/logo/", body), "بارگذاری لوگو ممکن نشد.");
  }

  const canContinue = multi === false || (multi === true && domains.length > 0);

  return (
    <StepCard title="شرکت و حوزه‌ها" intro="نام شرکت را بررسی کنید، لوگو بگذارید و بگویید شرکت شما حوزه‌بندی دارد یا نه.">
      {error && <DarkError message={error} />}

      <form onSubmit={saveName} className="flex gap-2">
        <input
          aria-label="نام شرکت"
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            setSaved(false);
          }}
          maxLength={255}
          className={darkInput}
        />
        <button type="submit" disabled={busy || !name.trim() || name.trim() === company.name} className={`${ghostButton} shrink-0`}>
          {saved ? "ذخیره شد ✓" : "ذخیرهٔ نام"}
        </button>
      </form>

      <div className="flex items-center gap-4">
        {company.logo_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={company.logo_url} alt="لوگوی شرکت" className="h-16 w-16 rounded-lg border border-line bg-white object-contain p-1" />
        ) : (
          <span className="flex h-16 w-16 items-center justify-center rounded-lg border border-dashed border-line text-xs text-slate-500">
            بدون لوگو
          </span>
        )}
        <div className="flex flex-wrap gap-2">
          <label className={`${ghostButton} cursor-pointer`}>
            {company.logo_url ? "تغییر لوگو" : "بارگذاری لوگو"}
            <input
              type="file"
              accept="image/png,image/jpeg"
              className="sr-only"
              disabled={busy}
              onChange={(e) => {
                void uploadLogo(e.target.files?.[0]);
                e.target.value = "";
              }}
            />
          </label>
          {company.logo_url && (
            <button
              type="button"
              disabled={busy}
              onClick={() => void run(() => apiDelete("/org/company/logo/"), "حذف لوگو ممکن نشد.")}
              className={ghostButton}
            >
              حذف لوگو
            </button>
          )}
        </div>
      </div>

      <fieldset className="space-y-2 rounded-lg border border-line p-4">
        <legend className="px-2 text-sm text-slate-300">آیا شرکت چند حوزه دارد؟</legend>
        <label className="flex items-center gap-2 text-sm text-slate-200">
          <input type="radio" name="multi" checked={multi === true} onChange={() => setMulti(true)} />
          بله، حوزه‌بندی دارد
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-200">
          <input
            type="radio"
            name="multi"
            checked={multi === false}
            disabled={domains.length > 0}
            onChange={() => setMulti(false)}
          />
          خیر، واحدها مستقیم زیر شرکت هستند
        </label>
        {domains.length > 0 && <p className="text-xs text-slate-500">برای انتخاب «خیر» ابتدا حوزه‌های افزوده‌شده را حذف کنید.</p>}
      </fieldset>

      {multi === true && (
        <div className="space-y-3">
          <AddNodeForm kind="DOMAIN" parentId={company.root} placeholder="نام حوزه، مثلاً «حوزه تولید»" onChanged={onChanged} />
          <ul className="space-y-1">
            {domains.map((domain) => (
              <li key={domain.id} className="flex items-center justify-between rounded-lg border border-line px-3 py-2 text-sm text-slate-200">
                {domain.name}
                <DeleteNodeButton node={domain} onChanged={onChanged} />
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex justify-end">
        <button type="button" onClick={onNext} disabled={!canContinue} className={primaryButton}>
          ادامه: واحدها
        </button>
      </div>
      {!canContinue && (
        <p className="text-xs text-slate-500">
          {multi === null ? "یکی از گزینه‌ها را انتخاب کنید." : "دست‌کم یک حوزه بیفزایید."}
        </p>
      )}
    </StepCard>
  );
}
