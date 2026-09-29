"use client";

import { useState } from "react";
import { ApiError, apiPatch } from "@/lib/api-client";
import { useCurrentUser } from "@/lib/current-user";
import { useApiQuery } from "@/lib/use-api-query";
import type { Company, DocumentDefaults } from "@/lib/organization";
import { EmptyBanner, LoadingBanner } from "@/components/StatusBanner";
import { LogoSection } from "@/components/designer/LogoSection";
import { FieldLabel, inputClass } from "@/components/designer/ui";
import { FileText, PanelBottom, PanelTop, Save, Settings2 } from "lucide-react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { cardClass } from "@/components/ui/Card";
import { FormSection } from "@/components/ui/FormSection";
import { PageHeader } from "@/components/ui/PageHeader";
import { cx } from "@/components/ui/cx";

/**
 * «تنظیمات». V_1.0 had the button but never wired it (main.py:938). It now holds
 * the document defaults (Phase 11, ADR-011): what every new document starts with.
 */
export default function SettingsPage() {
  const [reload, setReload] = useState(0);
  const company = useApiQuery<Company>("/org/company/", reload);

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader title="تنظیمات" subtitle="آنچه هر مستند تازه با آن شروع می‌شود." />
      {company.loading ? (
        <LoadingBanner />
      ) : !company.data ? (
        <EmptyBanner message="شرکت هنوز راه‌اندازی نشده است؛ پس از راه‌اندازی، پیش‌فرض‌های مستندات را اینجا تعیین کنید." />
      ) : (
        <DocumentDefaultsCard company={company.data} onSaved={() => setReload((n) => n + 1)} />
      )}
    </div>
  );
}

function DocumentDefaultsCard({ company, onSaved }: { company: Company; onSaved: () => void }) {
  const { can } = useCurrentUser();
  const canEdit = can("manage_organization");
  const [draft, setDraft] = useState<DocumentDefaults>(company.document_defaults);
  const [logoUrl, setLogoUrl] = useState(company.logo_url);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const dirty = JSON.stringify(draft) !== JSON.stringify(company.document_defaults);
  const set = (patch: Partial<DocumentDefaults>) => {
    setDraft((current) => ({ ...current, ...patch }));
    setMessage(null);
  };

  async function save() {
    setSaving(true);
    setMessage(null);
    try {
      await apiPatch<Company>("/org/company/document-defaults/", draft);
      setMessage({ ok: true, text: "پیش‌فرض‌ها ذخیره شد؛ از مستند بعدی که ایجاد شود به کار می‌رود." });
      onSaved();
    } catch (err) {
      setMessage({ ok: false, text: err instanceof ApiError ? err.message : "ذخیرهٔ پیش‌فرض‌ها ممکن نشد." });
    } finally {
      setSaving(false);
    }
  }

  const text = (key: "doc_footnote1" | "doc_footnote2" | "form_subtitle", label: string, placeholder: string) => (
    <label className="block">
      <FieldLabel>{label}</FieldLabel>
      <input
        value={draft[key]}
        maxLength={255}
        disabled={!canEdit || saving}
        placeholder={placeholder}
        onChange={(event) => set({ [key]: event.target.value })}
        className={inputClass}
      />
    </label>
  );

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_19rem] lg:items-start">
      <section aria-labelledby="defaults-title" className={cx(cardClass, "overflow-hidden")}>
        <header className="flex items-start gap-3 border-b border-slate-100 px-5 py-5 sm:px-6">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700 ring-1 ring-brand-600/10">
            <Settings2 className="size-5" />
          </span>
          <div>
            <h2 id="defaults-title" className="text-lg font-bold text-slate-900">
              پیش‌فرض‌های مستندات
            </h2>
            <p className="mt-1 text-sm leading-7 text-slate-500">
              هر مستندِ تازه با این لوگو و پاورقی‌ها شروع می‌شود و در هر فرمِ تازه، سربرگ هم از اینجا پر می‌شود. پس از ایجاد، در خود
              مستند قابل تغییرند؛ تغییر این پیش‌فرض‌ها مستندهای موجود را تغییر نمی‌دهد.
            </p>
          </div>
        </header>

        {!canEdit && (
          <div className="px-5 pt-5 sm:px-6">
            <Alert tone="warning">تغییر این تنظیمات فقط با دسترسی «مدیریت ساختار سازمانی» ممکن است.</Alert>
          </div>
        )}

        <FormSection step={1} title="لوگو" description="همان لوگوی شرکت؛ بلافاصله ذخیره می‌شود.">
          <LogoSection endpoint="/org/company/logo/" logoUrl={logoUrl} canEdit={canEdit} onChange={setLogoUrl} alt="لوگوی شرکت" />
        </FormSection>

        <FormSection step={2} title="پاورقی" description="دو متنی که پایین هر صفحه چاپ می‌شوند.">
          <div className="grid gap-4 sm:grid-cols-2">
            {text("doc_footnote1", "متن آزاد", "مثال: واحد برنامه ریزی شرکت")}
            {text("doc_footnote2", "متن دلخواه", "مثال: این مستند کنترل شده است")}
          </div>
        </FormSection>

        <FormSection step={3} title="سربرگ فرم‌ها" description="برای مستندهای گروه فرم.">
          {text("form_subtitle", "زیرعنوان سربرگ", "مثال: واحد منابع انسانی")}
          <label
            className={cx(
              "flex min-h-12 cursor-pointer items-center gap-3 rounded-xl border px-3.5 py-2.5 text-sm transition-colors duration-150",
              draft.form_show_letter_box ? "border-brand-300 bg-brand-50/60" : "border-slate-200 hover:border-slate-300",
              (!canEdit || saving) && "cursor-not-allowed opacity-60",
            )}
          >
            <input
              type="checkbox"
              className="peer sr-only"
              checked={draft.form_show_letter_box}
              disabled={!canEdit || saving}
              onChange={(event) => set({ form_show_letter_box: event.target.checked })}
            />
            <span
              aria-hidden
              className="relative h-5 w-9 shrink-0 rounded-full bg-slate-300 transition-colors duration-200 peer-checked:bg-brand-600 peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-brand-500 after:absolute after:top-0.5 after:right-0.5 after:size-4 after:rounded-full after:bg-white after:shadow after:transition-transform after:duration-200 peer-checked:after:-translate-x-4"
            />
            <span className="text-slate-700">شماره / تاریخ / پیوست در بالای صفحهٔ اول</span>
          </label>
        </FormSection>

        {canEdit && (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 bg-slate-50/70 px-5 py-4 sm:px-6">
            <span aria-live="polite" className="text-sm">
              {message ? (
                <span className={cx("animate-fade-in", message.ok ? "text-emerald-700" : "text-rose-700")}>{message.text}</span>
              ) : dirty ? (
                <span className="inline-flex items-center gap-1.5 text-amber-700">
                  <span aria-hidden className="size-2 rounded-full bg-amber-500" />
                  تغییرات ذخیره‌نشده
                </span>
              ) : null}
            </span>
            <Button variant="primary" icon={<Save />} onClick={() => void save()} disabled={!dirty} loading={saving} className="px-6">
              {saving ? "در حال ذخیره..." : "ذخیره"}
            </Button>
          </div>
        )}
      </section>

      <PagePreview
        logoUrl={logoUrl}
        companyName={company.name}
        subtitle={draft.form_subtitle}
        letterBox={draft.form_show_letter_box}
        footnote1={draft.doc_footnote1}
        footnote2={draft.doc_footnote2}
      />
    </div>
  );
}

/** A small A4 sheet showing where each default lands: the header (logo, company, subtitle, the letter
 *  box) and the footer (the two footnotes). A sketch, not the printed layout. */
function PagePreview({
  logoUrl,
  companyName,
  subtitle,
  letterBox,
  footnote1,
  footnote2,
}: {
  logoUrl: string | null;
  companyName: string;
  subtitle: string;
  letterBox: boolean;
  footnote1: string;
  footnote2: string;
}) {
  return (
    <aside aria-label="نمای کلی صفحه" className="space-y-3 lg:sticky lg:top-4">
      <p className="flex items-center gap-1.5 px-1 text-xs text-slate-500">
        <FileText className="size-3.5" />
        نمای کلی صفحهٔ یک فرم
      </p>
      <div className="rounded-2xl bg-[radial-gradient(circle_at_1px_1px,rgb(148_163_184/0.35)_1px,transparent_0)] bg-[length:16px_16px] bg-slate-100 p-4 ring-1 ring-slate-200/70">
        <div className="mx-auto flex aspect-[210/297] w-full max-w-64 flex-col rounded-sm bg-white p-3 text-[7px] leading-tight text-slate-700 shadow-[0_1px_3px_rgb(15_23_42/0.12),0_12px_32px_-12px_rgb(15_23_42/0.35)]">
          <div className="flex items-stretch border border-slate-700">
            <div className="flex w-8 items-center justify-center border-e border-slate-700 p-0.5">
              {logoUrl ? (
                // eslint-disable-next-line @next/next/no-img-element -- an authenticated API image, not a static asset
                <img src={logoUrl} alt="" className="max-h-6 max-w-full object-contain" />
              ) : (
                <span className="size-5 rounded-sm bg-slate-100" />
              )}
            </div>
            <div className="flex flex-1 flex-col items-center justify-center py-1 text-center">
              <span className="text-slate-400">{companyName}</span>
              <span className="text-[8px] font-bold text-slate-900">عنوان فرم</span>
              {subtitle && <span className="text-slate-500 animate-fade-in">{subtitle}</span>}
            </div>
            <div className="flex w-10 flex-col border-s border-slate-700">
              {[0, 1, 2].map((i) => (
                <span key={i} className={cx("flex-1", i > 0 && "border-t border-slate-300")} />
              ))}
            </div>
          </div>
          {letterBox && (
            <div className="mt-1 flex flex-col items-end gap-0.5 animate-fade-in">
              {["شماره", "تاریخ", "پیوست"].map((label) => (
                <span key={label} className="flex items-center gap-1">
                  {label}:
                  <span className="inline-block w-8 border-b border-dotted border-slate-400" />
                </span>
              ))}
            </div>
          )}
          <div className="mt-2 flex-1 space-y-1.5">
            {[11, 9, 10, 7, 9, 8].map((w, i) => (
              <span key={i} className="block h-1 rounded-full bg-slate-100" style={{ width: `${w * 9}%` }} />
            ))}
          </div>
          <div className="mt-2 flex items-end justify-between border-t border-slate-700 pt-1">
            <div className="min-w-0 space-y-0.5 text-slate-500">
              <span className="block truncate">{footnote1 || "متن آزاد"}</span>
              <span className="block truncate">{footnote2 || "متن دلخواه"}</span>
            </div>
            <span className="size-5 shrink-0 border border-dashed border-slate-300" />
          </div>
        </div>
      </div>
      <div className="flex flex-wrap gap-3 px-1 text-xs text-slate-500">
        <span className="inline-flex items-center gap-1">
          <PanelTop className="size-3.5" /> سربرگ
        </span>
        <span className="inline-flex items-center gap-1">
          <PanelBottom className="size-3.5" /> پاورقی
        </span>
      </div>
    </aside>
  );
}
