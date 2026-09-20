"use client";

import { officialPdfAction } from "@/lib/pdf";
import type { DocumentRow, PdfStatus } from "@/lib/types";

const NO_ACCESS = "دسترسی لازم برای ساخت PDF را ندارید.";

const primary = "rounded bg-slate-900 px-3 py-1 text-xs font-medium text-white hover:bg-slate-700";
const secondary = "rounded border border-slate-300 bg-white px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50";
const disabled = "cursor-not-allowed rounded bg-slate-200 px-3 py-1 text-xs font-medium text-slate-500";

interface Props {
  row: DocumentRow;
  /** The official PDF's latest known state (a build started here overrides the row's). */
  status: PdfStatus;
  canPrint: boolean;
  previewing: boolean;
  onPrint: () => void;
  onRebuild: () => void;
  onPreview: () => void;
}

/**
 * The register row's PDF buttons (Phase 4):
 *  - چاپ — only on a finalized row. Builds the issued PDF on demand («ساخت PDF»,
 *    a Celery task), then opens it; a ready PDF can be rebuilt.
 *  - نمایش — a watermarked «پیش‌نمایش» of any row whose body has been saved,
 *    drafts included. It never replaces the issued PDF.
 * Nothing here renders on page load: the list only reads `pdf_status`.
 */
export function PdfActions({ row, status, canPrint, previewing, onPrint, onRebuild, onPreview }: Props) {
  const official = officialPdfAction(status);

  return (
    <>
      {row.action === "print" && (
        <>
          <button
            type="button"
            onClick={onPrint}
            disabled={!canPrint || official.mode === "busy"}
            aria-busy={official.mode === "busy"}
            title={!canPrint ? NO_ACCESS : undefined}
            className={!canPrint || official.mode === "busy" ? disabled : primary}
          >
            {official.label}
          </button>
          {status === "ready" && canPrint && (
            <button type="button" onClick={onRebuild} className={secondary}>
              بازسازی
            </button>
          )}
        </>
      )}
      {row.content_saved_at && (
        <button
          type="button"
          onClick={onPreview}
          disabled={!canPrint || previewing}
          aria-busy={previewing}
          title={!canPrint ? NO_ACCESS : "پیش‌نمایش PDF با واترمارک"}
          className={!canPrint || previewing ? disabled : secondary}
        >
          {previewing ? "در حال ساخت…" : "نمایش"}
        </button>
      )}
    </>
  );
}
