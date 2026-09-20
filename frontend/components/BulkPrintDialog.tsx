"use client";

import { Code } from "@/components/Code";
import { ErrorBanner } from "@/components/StatusBanner";
import { downloadUrl, preflightPath, type BulkSelection } from "@/lib/bulk-print";
import { useApiQuery } from "@/lib/use-api-query";
import type { BulkPrintPreflight } from "@/lib/types";

/**
 * چاپ لیست: says what a bulk print would contain, then downloads the ZIP. Only
 * PDFs that already exist are packed — nothing is built here; documents without a
 * PDF are listed with the reason so they can be built first.
 */
export function BulkPrintDialog({
  selection,
  label,
  onClose,
}: {
  selection: BulkSelection;
  label: string;
  onClose: () => void;
}) {
  const { data, error, loading } = useApiQuery<BulkPrintPreflight>(preflightPath(selection));

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="چاپ لیست"
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/50 p-4 pt-20"
      onKeyDown={(event) => event.key === "Escape" && onClose()}
      onClick={(event) => event.target === event.currentTarget && onClose()}
    >
      <div className="w-full max-w-lg space-y-4 rounded-lg bg-white p-5 shadow-xl">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">چاپ لیست</h2>
          <p className="mt-1 text-sm text-slate-500">{label}</p>
        </div>

        {loading && <p className="text-sm text-slate-600">در حال بررسی...</p>}
        {error && <ErrorBanner message={error} />}

        {data && (
          <>
            <p className="text-sm leading-6 text-slate-700">
              <span className="font-semibold text-green-700">{data.ready}</span> PDF آمادهٔ دانلود است
              {data.missing.length > 0 && (
                <>
                  {" "}
                  و برای <span className="font-semibold text-amber-700">{data.missing.length}</span> مستند PDF وجود ندارد
                </>
              )}
              . فقط PDFهای ساخته‌شده در فایل ZIP قرار می‌گیرند؛ چیزی ساخته نمی‌شود.
            </p>

            {data.truncated && (
              <p role="status" className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                از {data.total} مستند، فقط {data.cap} مورد نخست (به ترتیب کد) بررسی شد. برای بقیه، انتخاب را محدودتر کنید.
              </p>
            )}

            {data.missing.length > 0 && (
              <div className="max-h-56 overflow-y-auto rounded border border-slate-200">
                <ul className="divide-y divide-slate-100 text-sm">
                  {data.missing.map((item) => (
                    <li key={item.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2">
                      <Code>{item.full_code}</Code>
                      <span className="min-w-[8rem] flex-1 text-slate-800">{item.title}</span>
                      <span className="text-xs text-amber-700">{item.reason_label}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-slate-300 bg-white px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
          >
            بستن
          </button>
          <button
            type="button"
            disabled={!data || data.ready === 0}
            onClick={() => {
              // A plain navigation: the browser sends its cookie and saves the ZIP;
              // the page stays put (Content-Disposition: attachment).
              window.location.assign(downloadUrl(selection));
              onClose();
            }}
            className="rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {data ? `دانلود ZIP (${data.ready} فایل)` : "دانلود ZIP"}
          </button>
        </div>
      </div>
    </div>
  );
}
