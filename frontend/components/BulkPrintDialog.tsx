"use client";

import { Code } from "@/components/Code";
import { Download } from "lucide-react";
import { ErrorBanner } from "@/components/StatusBanner";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogFooter } from "@/components/ui/Dialog";
import { SkeletonLines } from "@/components/ui/Skeleton";
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
    <Dialog label="چاپ لیست" title="چاپ لیست" description={label} onClose={onClose}>
      {loading && (
        <div role="status" className="space-y-3">
          <p className="text-sm text-slate-500">در حال بررسی...</p>
          <SkeletonLines rows={2} />
        </div>
      )}
      {error && <ErrorBanner message={error} />}

      {data && (
        <>
          <p className="text-sm leading-7 text-slate-700">
            <span className="font-bold text-emerald-700">{data.ready}</span> PDF آمادهٔ دانلود است
            {data.missing.length > 0 && (
              <>
                {" "}
                و برای <span className="font-bold text-amber-700">{data.missing.length}</span> مستند PDF وجود ندارد
              </>
            )}
            . فقط PDFهای ساخته‌شده در فایل ZIP قرار می‌گیرند؛ چیزی ساخته نمی‌شود.
          </p>

          {data.truncated && (
            <Alert tone="warning" role="status">
              از {data.total} مستند، فقط {data.cap} مورد نخست (به ترتیب کد) بررسی شد. برای بقیه، انتخاب را محدودتر کنید.
            </Alert>
          )}

          {data.missing.length > 0 && (
            <div className="max-h-56 overflow-y-auto rounded-xl border border-slate-200">
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

      <DialogFooter>
        <Button onClick={onClose}>بستن</Button>
        <Button
          variant="primary"
          icon={<Download />}
          disabled={!data || data.ready === 0}
          onClick={() => {
            // A plain navigation: the browser sends its cookie and saves the ZIP;
            // the page stays put (Content-Disposition: attachment).
            window.location.assign(downloadUrl(selection));
            onClose();
          }}
        >
          {data ? `دانلود ZIP (${data.ready} فایل)` : "دانلود ZIP"}
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
