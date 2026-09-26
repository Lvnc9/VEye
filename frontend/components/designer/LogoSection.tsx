"use client";

import { useRef, useState } from "react";
import { ApiError, apiDelete, apiUpload } from "@/lib/api-client";
import type { ContentResponse } from "@/lib/types";

/** «سربرگ»: the document's logo. It is saved as soon as it is picked or removed,
 *  independently of the body's «ذخیره». */
export function LogoSection({
  documentId,
  logoUrl,
  canEdit,
  onChange,
}: {
  documentId: number;
  logoUrl: string | null;
  canEdit: boolean;
  onChange: (logoUrl: string | null) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  async function changeLogo(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("logo", file);
      const response = await apiUpload<ContentResponse>(`/documents/${documentId}/logo/`, form);
      onChange(response.logo_url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "بارگذاری لوگو ممکن نشد.");
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  async function removeLogo() {
    setBusy(true);
    setError(null);
    try {
      const response = await apiDelete<ContentResponse>(`/documents/${documentId}/logo/`);
      onChange(response.logo_url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "حذف لوگو ممکن نشد.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-4">
      <div className="flex h-24 w-24 items-center justify-center overflow-hidden rounded border border-slate-200 bg-slate-50">
        {logoUrl ? (
          // eslint-disable-next-line @next/next/no-img-element -- an authenticated API image, not a static asset
          <img src={logoUrl} alt="لوگوی مستند" className="max-h-full max-w-full object-contain" />
        ) : (
          <span className="text-xs text-slate-400">بدون لوگو</span>
        )}
      </div>
      {canEdit && (
        <div className="space-y-2">
          <input
            ref={input}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            hidden
            onChange={(event) => void changeLogo(event.target.files?.[0])}
          />
          <div className="flex gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => input.current?.click()}
              className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100 disabled:opacity-50"
            >
              {logoUrl ? "تغییر لوگو" : "انتخاب لوگو"}
            </button>
            {logoUrl && (
              <button
                type="button"
                disabled={busy}
                onClick={() => void removeLogo()}
                className="rounded border border-red-200 bg-white px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 disabled:opacity-50"
              >
                حذف لوگو
              </button>
            )}
          </div>
          <p className="text-xs text-slate-500">تصویر PNG یا JPEG؛ لوگو بلافاصله ذخیره می‌شود.</p>
          {error && <p className="text-xs text-red-600">{error}</p>}
        </div>
      )}
    </div>
  );
}
