"use client";

import { useState } from "react";
import { ApiError, apiPatch } from "@/lib/api-client";
import { useCurrentUser } from "@/lib/current-user";
import { useApiQuery } from "@/lib/use-api-query";
import type { Company, DocumentDefaults } from "@/lib/organization";
import { EmptyBanner, LoadingBanner } from "@/components/StatusBanner";
import { LogoSection } from "@/components/designer/LogoSection";
import { FieldLabel, inputClass } from "@/components/designer/ui";

/**
 * «تنظیمات». V_1.0 had the button but never wired it (main.py:938). It now holds
 * the document defaults (Phase 11, ADR-011): what every new document starts with.
 */
export default function SettingsPage() {
  const [reload, setReload] = useState(0);
  const company = useApiQuery<Company>("/org/company/", reload);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">تنظیمات</h1>
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
    <section className="space-y-5 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <header>
        <h2 className="text-lg font-semibold text-slate-900">پیش‌فرض‌های مستندات</h2>
        <p className="mt-1 text-sm text-slate-500">
          هر مستندِ تازه با این لوگو و پاورقی‌ها شروع می‌شود و در هر فرمِ تازه، سربرگ هم از اینجا پر می‌شود. پس از ایجاد، در خود مستند
          قابل تغییرند؛ تغییر این پیش‌فرض‌ها مستندهای موجود را تغییر نمی‌دهد.
        </p>
      </header>

      {!canEdit && (
        <p className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          تغییر این تنظیمات فقط با دسترسی «مدیریت ساختار سازمانی» ممکن است.
        </p>
      )}

      <div className="space-y-2">
        <FieldLabel>لوگو (همان لوگوی شرکت)</FieldLabel>
        <LogoSection endpoint="/org/company/logo/" logoUrl={logoUrl} canEdit={canEdit} onChange={setLogoUrl} alt="لوگوی شرکت" />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {text("doc_footnote1", "پاورقی — متن آزاد", "مثال: واحد برنامه ریزی شرکت")}
        {text("doc_footnote2", "پاورقی — متن دلخواه", "مثال: این مستند کنترل شده است")}
      </div>

      <div className="space-y-3 border-t border-slate-200 pt-4">
        <h3 className="text-sm font-semibold text-slate-800">سربرگ فرم‌ها</h3>
        {text("form_subtitle", "زیرعنوان سربرگ", "مثال: واحد منابع انسانی")}
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={draft.form_show_letter_box}
            disabled={!canEdit || saving}
            onChange={(event) => set({ form_show_letter_box: event.target.checked })}
          />
          شماره / تاریخ / پیوست در بالای صفحهٔ اول
        </label>
      </div>

      {canEdit && (
        <div className="flex flex-wrap items-center gap-3 border-t border-slate-200 pt-4">
          <button
            type="button"
            onClick={() => void save()}
            disabled={!dirty || saving}
            className="rounded bg-purple-800 px-6 py-2 text-sm font-semibold text-white hover:bg-purple-900 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? "در حال ذخیره..." : "ذخیره"}
          </button>
          {message && <span className={`text-sm ${message.ok ? "text-green-700" : "text-red-700"}`}>{message.text}</span>}
        </div>
      )}
    </section>
  );
}
