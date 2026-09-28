"use client";

import { useRef, useState } from "react";
import { ApiError, apiDelete, apiUpload } from "@/lib/api-client";
import { buttonClass } from "@/components/ui/Button";

/** A logo picker: saved as soon as a file is picked or removed, independently of
 *  any «ذخیره». `endpoint` takes POST (multipart `logo`) and DELETE, and answers
 *  with the new `logo_url` — a document's (`/documents/{id}/logo/`) or the
 *  company's default (`/org/company/logo/`). */
export function LogoSection({
  endpoint,
  logoUrl,
  canEdit,
  onChange,
  alt = "لوگوی مستند",
}: {
  endpoint: string;
  logoUrl: string | null;
  canEdit: boolean;
  onChange: (logoUrl: string | null) => void;
  alt?: string;
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
      const response = await apiUpload<{ logo_url: string | null }>(endpoint, form);
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
      const response = await apiDelete<{ logo_url: string | null }>(endpoint);
      onChange(response.logo_url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "حذف لوگو ممکن نشد.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-4">
      <div className="flex size-24 items-center justify-center overflow-hidden rounded-xl border border-dashed border-slate-300 bg-[radial-gradient(circle_at_1px_1px,rgb(148_163_184/0.3)_1px,transparent_0)] bg-[length:10px_10px] bg-slate-50">
        {logoUrl ? (
          // eslint-disable-next-line @next/next/no-img-element -- an authenticated API image, not a static asset
          <img src={logoUrl} alt={alt} className="max-h-full max-w-full object-contain" />
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
              className={buttonClass({ size: "sm" })}
            >
              {logoUrl ? "تغییر لوگو" : "انتخاب لوگو"}
            </button>
            {logoUrl && (
              <button
                type="button"
                disabled={busy}
                onClick={() => void removeLogo()}
                className={buttonClass({ size: "sm", variant: "danger-ghost" })}
              >
                حذف لوگو
              </button>
            )}
          </div>
          <p className="text-xs text-slate-500">تصویر PNG یا JPEG؛ لوگو بلافاصله ذخیره می‌شود.</p>
          {error && <p className="text-xs text-rose-600">{error}</p>}
        </div>
      )}
    </div>
  );
}
