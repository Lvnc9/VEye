"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { useState } from "react";
import { useCurrentUser } from "@/lib/current-user";
import { formatJalali, formatJalaliDateTime } from "@/lib/jalali";
import { Code } from "@/components/Code";
import { StatusBadge } from "@/components/StatusBadge";
import { WorkflowActions } from "@/components/WorkflowActions";
import { WorkflowTimeline } from "@/components/WorkflowTimeline";
import { OwnerNodeSelect, useOwnerNodeChoices } from "@/components/OwnerNodeSelect";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
import { apiPost, ApiError } from "@/lib/api-client";
import type { DesignerDocument } from "./useDesignerDocument";
import { ArrowRight, Eye, Redo2, RotateCcw, Save, Undo2 } from "lucide-react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { cardClass } from "@/components/ui/Card";
import { cx } from "@/components/ui/cx";

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
  const { choices: ownerChoices } = useOwnerNodeChoices();
  const [ownerError, setOwnerError] = useState<string | null>(null);
  const [ownerSaving, setOwnerSaving] = useState(false);

  /** «گرهٔ مالک»: the node the document belongs to; a draft's owner can be changed to another the person may pick. */
  async function changeOwner(id: number | null) {
    if (id === null) return;
    setOwnerError(null);
    setOwnerSaving(true);
    try {
      await apiPost(`/documents/${content.document.id}/owner-node/`, { owner_node: id });
      void doc.reload();
    } catch (err) {
      setOwnerError(err instanceof ApiError ? err.message : "تغییر گرهٔ مالک ممکن نشد.");
    } finally {
      setOwnerSaving(false);
    }
  }

  if (doc.reloading) return <LoadingBanner />;
  if (doc.loadError) return <ErrorBanner message={doc.loadError} />;

  const document = content.document;
  const saveBlocked = saving || pendingUploads > 0;
  const width = wide ? "max-w-7xl" : "max-w-4xl";

  return (
    <div className={`mx-auto ${width} space-y-6`}>
      <nav className="text-sm">
        <Link
          href="/documents"
          className="group inline-flex items-center gap-1.5 text-slate-500 transition-colors hover:text-slate-900"
        >
          <ArrowRight className="size-4 transition-transform duration-200 group-hover:translate-x-0.5" />
          بازگشت به فهرست مستندات
        </Link>
      </nav>

      <header className={cx(cardClass, "relative overflow-hidden p-5 sm:p-6")}>
        {/* A thin brand rule across the top of the document's header card. */}
        <div aria-hidden className="absolute inset-x-0 top-0 h-1 bg-gradient-to-l from-brand-500 via-indigo-400 to-emerald-400 opacity-80" />
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-2xl font-bold leading-10 text-slate-900">{document.title}</h1>
            <p className="mt-0.5 text-sm text-slate-500">
              {document.group_label} · {document.category_label}
            </p>
            {(document.owner_node || (canEdit && ownerChoices.length > 0)) && (
              <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-slate-600">
                <span>گرهٔ مالک:</span>
                {canEdit && ownerChoices.length > 0 ? (
                  <OwnerNodeSelect
                    value={document.owner_node?.id ?? null}
                    choices={ownerChoices}
                    disabled={ownerSaving || dirty}
                    onChange={changeOwner}
                    className="w-64 max-w-full"
                  />
                ) : (
                  <span className="font-medium text-slate-800">
                    {document.owner_node?.kind_label} · {document.owner_node?.name}
                  </span>
                )}
                {dirty && canEdit && ownerChoices.length > 0 && (
                  <span className="text-xs text-slate-500">ابتدا تغییرات را ذخیره کنید.</span>
                )}
              </div>
            )}
            {ownerError && <p className="mt-1 text-sm text-rose-700">{ownerError}</p>}
          </div>
          <div className="flex items-center gap-2">
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
        <Alert
          tone="danger"
          role="status"
          title={
            <>
              این مستند مرجوع شده است — {document.return_note.by}
              {document.return_note.by_title ? ` (${document.return_note.by_title})` : ""} ·{" "}
              {formatJalali(document.return_note.at)}
            </>
          }
        >
          <p className="whitespace-pre-wrap">{document.return_note.reason}</p>
          <p className="text-rose-700">پس از اصلاح، مستند را دوباره برای تایید ارسال کنید.</p>
        </Alert>
      )}

      <WorkflowTimeline documentId={document.id} version={document.status} />

      {!canEdit && (
        <Alert tone="warning">
          {content.editable
            ? "شما دسترسی ویرایش این مستند را ندارید؛ فقط می‌توانید آن را ببینید."
            : "این مستند دیگر پیش‌نویس نیست و محتوای آن قفل شده است؛ فقط می‌توانید آن را ببینید."}
        </Alert>
      )}

      {doc.recovery?.kind === "offer" && canEdit && (
        <Alert
          tone="info"
          role="status"
          actions={
            <>
              <Button size="sm" variant="primary" icon={<RotateCcw />} onClick={doc.restoreDraft}>
                بازیابی
              </Button>
              <Button size="sm" variant="ghost" onClick={doc.discardDraft}>
                نادیده گرفتن
              </Button>
            </>
          }
        >
          تغییرات ذخیره‌نشده‌ای از {formatJalaliDateTime(new Date(doc.recovery.at))} در همین مرورگر پیدا شد.
        </Alert>
      )}
      {doc.recovery?.kind === "stale" && (
        <Alert
          tone="warning"
          role="status"
          actions={
            <Button size="sm" variant="ghost" onClick={doc.discardDraft}>
              بستن
            </Button>
          }
        >
          تغییرات ذخیره‌نشده‌ای از {formatJalaliDateTime(new Date(doc.recovery.at))} پیدا شد، اما مستند پس از آن ذخیره شده است؛
          برای اینکه کار دیگران پاک نشود، کنار گذاشته شد.
        </Alert>
      )}

      {doc.conflict && (
        <Alert
          tone="danger"
          actions={
            <Button size="sm" variant="danger" icon={<RotateCcw />} onClick={() => void doc.reload()}>
              بارگذاری آخرین نسخه (تغییرات ذخیره‌نشده از بین می‌رود)
            </Button>
          }
        >
          این مستند در همین فاصله توسط شخص دیگری ذخیره شده است. برای ادامه باید آخرین نسخه را بارگذاری کنید.
        </Alert>
      )}

      {children}

      {/* Sticky inside the content column (not fixed to the window, which would
          slide it under the sidebar). The negative margins cancel <main>'s padding
          (p-4 sm:p-6 md:p-8, app/(app)/layout.tsx) at every width, so the bar spans
          the column edge to edge without pushing the page sideways on a phone. */}
      <div className="sticky bottom-0 z-40 -mx-4 -mb-4 mt-6 border-t border-slate-200/80 bg-white/85 px-4 py-3 shadow-[0_-8px_24px_-12px_rgb(15_23_42/0.15)] backdrop-blur-md sm:-mx-6 sm:-mb-6 sm:px-6 md:-mx-8 md:-mb-8 md:px-8">
        <div className={`mx-auto flex ${width} flex-wrap items-center gap-2 sm:gap-3`}>
          {canEdit && (
            <>
              <Button
                variant="primary"
                icon={<Save />}
                onClick={() => void doc.save()}
                disabled={saveBlocked || !dirty}
                loading={saving}
                title={pendingUploads > 0 ? "تا پایان بارگذاری فایل‌ها صبر کنید." : "ذخیره و ادامهٔ ویرایش"}
                className="px-5"
              >
                {saving ? "در حال ذخیره..." : "ذخیره"}
              </Button>
              <Button
                variant="subtle"
                onClick={() => void doc.save({ andReturn: true })}
                disabled={saveBlocked || !dirty}
                title="ذخیره و بازگشت به فهرست مستندات"
              >
                ذخیره و بازگشت
              </Button>
              <span
                className="flex items-center rounded-lg border border-slate-300 bg-white shadow-xs"
                role="group"
                aria-label="واگرد و ازنو"
              >
                <button
                  type="button"
                  onClick={doc.undo}
                  disabled={!doc.canUndo || saving}
                  title="واگرد (Ctrl+Z)"
                  aria-label="واگرد"
                  className="flex size-10 items-center justify-center rounded-s-lg text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:bg-transparent"
                >
                  <Undo2 className="rtl-flip size-4" />
                </button>
                <span aria-hidden className="h-5 w-px bg-slate-200" />
                <button
                  type="button"
                  onClick={doc.redo}
                  disabled={!doc.canRedo || saving}
                  title="ازنو (Ctrl+Shift+Z)"
                  aria-label="ازنو"
                  className="flex size-10 items-center justify-center rounded-e-lg text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:bg-transparent"
                >
                  <Redo2 className="rtl-flip size-4" />
                </button>
              </span>
            </>
          )}
          <Button
            icon={<Eye />}
            onClick={doc.preview}
            disabled={!can("print_document") || dirty || saving}
            loading={previewing}
            title={
              !can("print_document")
                ? "دسترسی لازم برای ساخت PDF را ندارید."
                : dirty
                  ? "ابتدا تغییرات را ذخیره کنید؛ پیش‌نمایش آخرین نسخهٔ ذخیره‌شده را نشان می‌دهد."
                  : "پیش‌نمایش PDF با واترمارک"
            }
          >
            {previewing ? "در حال ساخت…" : "نمایش"}
          </Button>

          <span className="flex flex-wrap items-center gap-3 text-sm" aria-live="polite">
            {dirty && canEdit && (
              <span className="inline-flex items-center gap-1.5 text-amber-700 animate-fade-in">
                <span aria-hidden className="size-2 rounded-full bg-amber-500 shadow-[0_0_0_3px_rgb(245_158_11/0.2)]" />
                تغییرات ذخیره‌نشده
              </span>
            )}
            {pendingUploads > 0 && <span className="text-slate-500">در حال بارگذاری فایل...</span>}
            {notice && !dirty && (
              <span className="inline-flex items-center gap-1.5 text-emerald-700 animate-fade-in">
                <span aria-hidden className="size-2 rounded-full bg-emerald-500" />
                {notice}
              </span>
            )}
          </span>
          {saveErrors.length > 0 && (
            <ul className="w-full list-disc space-y-0.5 rounded-lg bg-rose-50 py-2 ps-8 pe-3 text-sm text-rose-800">
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
