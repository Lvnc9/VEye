"use client";

import { Eye, Printer, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { officialPdfAction } from "@/lib/pdf";
import type { DocumentRow, PdfStatus } from "@/lib/types";

const NO_ACCESS = "دسترسی لازم برای ساخت PDF را ندارید.";


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

  const busy = official.mode === "busy";
  return (
    <>
      {row.action === "print" && (
        <>
          <Button
            size="xs"
            variant="primary"
            onClick={onPrint}
            disabled={!canPrint}
            loading={busy}
            icon={<Printer />}
            title={!canPrint ? NO_ACCESS : undefined}
          >
            {official.label}
          </Button>
          {status === "ready" && canPrint && (
            <Button size="xs" onClick={onRebuild} icon={<RefreshCw />}>
              بازسازی
            </Button>
          )}
        </>
      )}
      {row.content_saved_at && (
        <Button
          size="xs"
          onClick={onPreview}
          disabled={!canPrint}
          loading={previewing}
          icon={<Eye />}
          title={!canPrint ? NO_ACCESS : "پیش‌نمایش PDF با واترمارک"}
        >
          {previewing ? "در حال ساخت…" : "نمایش"}
        </Button>
      )}
    </>
  );
}
