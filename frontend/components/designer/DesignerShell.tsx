"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { useCurrentUser } from "@/lib/current-user";
import { formatJalali } from "@/lib/jalali";
import { Code } from "@/components/Code";
import { StatusBadge } from "@/components/StatusBadge";
import { WorkflowActions } from "@/components/WorkflowActions";
import { WorkflowTimeline } from "@/components/WorkflowTimeline";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
import type { DesignerDocument } from "./useDesignerDocument";

/**
 * The frame every document body is edited in, whatever its kind: the header card
 * with the workflow buttons, the return / read-only / conflict banners, the
 * workflow timeline and the sticky save bar. The body goes in `children`.
 */
export function DesignerShell<S>({
  doc,
  wide = false,
  children,
}: {
  doc: DesignerDocument<S>;
  /** The form designer needs the room for its canvas and side panels. */
  wide?: boolean;
  children: ReactNode;
}) {
  const { can } = useCurrentUser();
  const { content, canEdit, dirty, saving, pendingUploads, previewing, notice, saveErrors } = doc;

  if (doc.reloading) return <LoadingBanner />;
  if (doc.loadError) return <ErrorBanner message={doc.loadError} />;

  const document = content.document;
  const saveBlocked = saving || pendingUploads > 0;
  const width = wide ? "max-w-7xl" : "max-w-4xl";

  return (
    <div className={`mx-auto ${width} space-y-6`}>
      <nav className="text-sm">
        <Link href="/documents" className="text-slate-500 hover:text-slate-800">
          ← بازگشت به فهرست مستندات
        </Link>
      </nav>

      <header className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">{document.title}</h1>
            <p className="mt-1 text-sm text-slate-500">
              {document.group_label} · {document.category_label}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Code>{document.full_code}</Code>
            <StatusBadge status={document.status} label={document.status_label} />
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2 empty:hidden">
          <WorkflowActions
            row={document}
            hold={dirty ? "ابتدا تغییرات را ذخیره کنید؛ امضا روی آخرین نسخهٔ ذخیره‌شده ثبت می‌شود." : undefined}
            onDone={(message) => {
              doc.setNotice(message);
              void doc.reload();
            }}
          />
        </div>
      </header>

      {document.return_note && (
        <div role="status" className="space-y-1 rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <p className="font-semibold">
            این مستند مرجوع شده است — {document.return_note.by}
            {document.return_note.by_title ? ` (${document.return_note.by_title})` : ""} ·{" "}
            {formatJalali(document.return_note.at)}
          </p>
          <p className="whitespace-pre-wrap">{document.return_note.reason}</p>
          <p className="text-red-700">پس از اصلاح، مستند را دوباره برای تایید ارسال کنید.</p>
        </div>
      )}

      <WorkflowTimeline documentId={document.id} version={document.status} />

      {!canEdit && (
        <div className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          {content.editable
            ? "شما دسترسی ویرایش این مستند را ندارید؛ فقط می‌توانید آن را ببینید."
            : "این مستند دیگر پیش‌نویس نیست و محتوای آن قفل شده است؛ فقط می‌توانید آن را ببینید."}
        </div>
      )}

      {doc.conflict && (
        <div className="space-y-2 rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <p>این مستند در همین فاصله توسط شخص دیگری ذخیره شده است. برای ادامه باید آخرین نسخه را بارگذاری کنید.</p>
          <button
            type="button"
            onClick={() => void doc.reload()}
            className="rounded bg-red-700 px-3 py-1.5 font-medium text-white hover:bg-red-800"
          >
            بارگذاری آخرین نسخه (تغییرات ذخیره‌نشده از بین می‌رود)
          </button>
        </div>
      )}

      {children}

      {/* Sticky inside the content column (not fixed to the window, which would
          slide it under the sidebar). The negative margins cancel <main>'s padding
          so the bar spans the column edge to edge. */}
      <div className="sticky bottom-0 z-40 -mx-8 -mb-8 mt-6 border-t border-slate-200 bg-white/95 px-8 py-3 backdrop-blur">
        <div className={`mx-auto flex ${width} flex-wrap items-center gap-3`}>
          {canEdit && (
            <button
              type="button"
              onClick={() => void doc.save()}
              disabled={saveBlocked || !dirty}
              title={pendingUploads > 0 ? "تا پایان بارگذاری فایل‌ها صبر کنید." : undefined}
              className="rounded bg-purple-800 px-6 py-2 text-sm font-semibold text-white hover:bg-purple-900 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? "در حال ذخیره..." : "ذخیره"}
            </button>
          )}
          <button
            type="button"
            onClick={doc.preview}
            disabled={!can("print_document") || dirty || saving || previewing}
            aria-busy={previewing}
            title={
              !can("print_document")
                ? "دسترسی لازم برای ساخت PDF را ندارید."
                : dirty
                  ? "ابتدا تغییرات را ذخیره کنید؛ پیش‌نمایش آخرین نسخهٔ ذخیره‌شده را نشان می‌دهد."
                  : "پیش‌نمایش PDF با واترمارک"
            }
            className="rounded border border-slate-300 bg-white px-6 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
          >
            {previewing ? "در حال ساخت…" : "نمایش"}
          </button>

          {dirty && canEdit && <span className="text-sm text-amber-700">تغییرات ذخیره‌نشده</span>}
          {pendingUploads > 0 && <span className="text-sm text-slate-500">در حال بارگذاری فایل...</span>}
          {notice && !dirty && <span className="text-sm text-green-700">{notice}</span>}
          {saveErrors.length > 0 && (
            <ul className="w-full list-disc space-y-0.5 ps-5 text-sm text-red-700">
              {saveErrors.map((message, i) => (
                <li key={i}>{message}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
