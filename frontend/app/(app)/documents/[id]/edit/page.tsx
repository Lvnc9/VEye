"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ApiError, apiDelete, apiGet, apiPut, apiUpload } from "@/lib/api-client";
import {
  canAddSection,
  fromResponse,
  moveSection,
  newSection,
  snapshot,
  toPayload,
  validate,
  type DesignerState,
} from "@/lib/designer";
import {
  SECTION_TYPES,
  SECTION_TYPE_LABELS,
  type ContentResponse,
  type DesignerSection,
  type SectionType,
} from "@/lib/types";
import { useCurrentUser } from "@/lib/current-user";
import { Code } from "@/components/Code";
import { StatusBadge } from "@/components/StatusBadge";
import { WorkflowActions } from "@/components/WorkflowActions";
import { WorkflowTimeline } from "@/components/WorkflowTimeline";
import { formatJalali } from "@/lib/jalali";
import { PdfBuildError, buildPdf, openPdfInTab } from "@/lib/pdf";
import { setFlash } from "@/lib/flash";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
import { BlockFrame } from "@/components/designer/BlockFrame";
import { ShortBlock } from "@/components/designer/ShortBlock";
import { LongBlock } from "@/components/designer/LongBlock";
import { ResponsibilitiesBlock } from "@/components/designer/ResponsibilitiesBlock";
import { ChangesBlock } from "@/components/designer/ChangesBlock";
import { AttachmentBlock } from "@/components/designer/AttachmentBlock";
import { FieldLabel, inputClass } from "@/components/designer/ui";

/** طراحی مستند — V_1.0's Poster screen (poster_01.py). */
export default function DocumentDesignerPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { can } = useCurrentUser();

  const [content, setContent] = useState<ContentResponse | null>(null);
  const [state, setState] = useState<DesignerState | null>(null);
  const [savedSnapshot, setSavedSnapshot] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [saving, setSaving] = useState(false);
  const [saveErrors, setSaveErrors] = useState<string[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);

  const [pendingUploads, setPendingUploads] = useState(0);
  const [logoBusy, setLogoBusy] = useState(false);
  const [logoError, setLogoError] = useState<string | null>(null);
  const logoInput = useRef<HTMLInputElement>(null);

  const applyResponse = useCallback((response: ContentResponse) => {
    const next = fromResponse(response);
    setContent(response);
    setState(next);
    setSavedSnapshot(snapshot(next));
    setConflict(false);
    setLoadError(null);
  }, []);

  // Initial load. State is only written from the async result, never
  // synchronously in the effect body (react-hooks/set-state-in-effect).
  useEffect(() => {
    let cancelled = false;
    apiGet<ContentResponse>(`/documents/${id}/content/`)
      .then((response) => {
        if (!cancelled) applyResponse(response);
      })
      .catch((err) => {
        if (!cancelled) setLoadError(err instanceof ApiError ? err.message : "دریافت مستند ممکن نشد.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id, applyResponse]);

  /** Re-fetch on demand (after a version conflict, or if the document was locked
   *  while we edited). Called from event handlers, so it may set state freely. */
  const reload = useCallback(async () => {
    setLoading(true);
    try {
      applyResponse(await apiGet<ContentResponse>(`/documents/${id}/content/`));
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "دریافت مستند ممکن نشد.");
    } finally {
      setLoading(false);
    }
  }, [id, applyResponse]);

  const dirty = state !== null && snapshot(state) !== savedSnapshot;

  // Closing the tab with unsaved work is the one way to lose it silently.
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const [previewing, setPreviewing] = useState(false);

  // نمایش: a watermarked preview of what was last *saved* (the server renders the
  // stored document), so it is held while there are unsaved edits.
  function preview() {
    setSaveErrors([]);
    setPreviewing(true);
    openPdfInTab(() => buildPdf(Number(id), "preview"))
      .catch((err) =>
        setSaveErrors([
          err instanceof ApiError || err instanceof PdfBuildError ? err.message : "ساخت پیش‌نمایش ممکن نشد.",
        ]),
      )
      .finally(() => setPreviewing(false));
  }

  const canEdit = Boolean(content?.editable) && can("create_document");
  const locked = !canEdit || saving;

  function updateSection<T extends DesignerSection>(key: string, updater: (section: T) => T) {
    setState((current) =>
      current
        ? { ...current, sections: current.sections.map((s) => (s.key === key ? updater(s as T) : s)) }
        : current,
    );
    setNotice(null);
  }

  function addSection(type: SectionType) {
    setState((current) => (current ? { ...current, sections: [...current.sections, newSection(type)] } : current));
    setNotice(null);
  }

  const trackUpload = useCallback(() => {
    setPendingUploads((n) => n + 1);
    return () => setPendingUploads((n) => n - 1);
  }, []);

  async function save() {
    if (!state || !content) return;
    const problems = validate(state);
    if (problems.length > 0) {
      setSaveErrors(problems);
      return;
    }

    setSaving(true);
    setSaveErrors([]);
    setNotice(null);
    try {
      const response = await apiPut<ContentResponse>(`/documents/${id}/content/`, toPayload(state));
      // Hand back the sections just sent so each block keeps its React key.
      const next = fromResponse(response, state.sections);
      setContent(response);
      setState(next);
      setSavedSnapshot(snapshot(next));
      // Like V_1.0 (poster_01.py show_pdf → change_to_documents1): once the document is
      // saved, go back to «ساخت مستند», where the register says it was saved.
      setFlash(`مستند ${response.document.full_code} ذخیره شد.`);
      router.push("/documents");
    } catch (err) {
      const code = err instanceof ApiError ? (err.data as { code?: string } | undefined)?.code : undefined;
      if (code === "version_conflict") setConflict(true);
      if (code === "content_locked") void reload(); // it moved past draft while we edited
      setSaveErrors([err instanceof ApiError ? err.message : "ذخیره مستند ممکن نشد."]);
    } finally {
      setSaving(false);
    }
  }

  async function changeLogo(file: File | undefined) {
    if (!file) return;
    setLogoBusy(true);
    setLogoError(null);
    try {
      const form = new FormData();
      form.append("logo", file);
      const response = await apiUpload<ContentResponse>(`/documents/${id}/logo/`, form);
      setContent((current) => (current ? { ...current, logo_url: response.logo_url } : current));
    } catch (err) {
      setLogoError(err instanceof ApiError ? err.message : "بارگذاری لوگو ممکن نشد.");
    } finally {
      setLogoBusy(false);
      if (logoInput.current) logoInput.current.value = "";
    }
  }

  async function removeLogo() {
    setLogoBusy(true);
    setLogoError(null);
    try {
      const response = await apiDelete<ContentResponse>(`/documents/${id}/logo/`);
      setContent((current) => (current ? { ...current, logo_url: response.logo_url } : current));
    } catch (err) {
      setLogoError(err instanceof ApiError ? err.message : "حذف لوگو ممکن نشد.");
    } finally {
      setLogoBusy(false);
    }
  }

  if (loading) return <LoadingBanner />;
  if (loadError || !content || !state) return <ErrorBanner message={loadError ?? "مستند یافت نشد."} />;

  const document = content.document;
  const saveBlocked = saving || pendingUploads > 0;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
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
              setNotice(message);
              void reload();
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

      {conflict && (
        <div className="space-y-2 rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <p>این مستند در همین فاصله توسط شخص دیگری ذخیره شده است. برای ادامه باید آخرین نسخه را بارگذاری کنید.</p>
          <button
            type="button"
            onClick={() => void reload()}
            className="rounded bg-red-700 px-3 py-1.5 font-medium text-white hover:bg-red-800"
          >
            بارگذاری آخرین نسخه (تغییرات ذخیره‌نشده از بین می‌رود)
          </button>
        </div>
      )}

      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold text-slate-900">سربرگ</h2>
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex h-24 w-24 items-center justify-center overflow-hidden rounded border border-slate-200 bg-slate-50">
            {content.logo_url ? (
              // eslint-disable-next-line @next/next/no-img-element -- an authenticated API image, not a static asset
              <img src={content.logo_url} alt="لوگوی مستند" className="max-h-full max-w-full object-contain" />
            ) : (
              <span className="text-xs text-slate-400">بدون لوگو</span>
            )}
          </div>
          {canEdit && (
            <div className="space-y-2">
              <input
                ref={logoInput}
                type="file"
                accept="image/png,image/jpeg,image/webp"
                hidden
                onChange={(event) => void changeLogo(event.target.files?.[0])}
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={logoBusy}
                  onClick={() => logoInput.current?.click()}
                  className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                >
                  {content.logo_url ? "تغییر لوگو" : "انتخاب لوگو"}
                </button>
                {content.logo_url && (
                  <button
                    type="button"
                    disabled={logoBusy}
                    onClick={() => void removeLogo()}
                    className="rounded border border-red-200 bg-white px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 disabled:opacity-50"
                  >
                    حذف لوگو
                  </button>
                )}
              </div>
              <p className="text-xs text-slate-500">تصویر PNG یا JPEG؛ لوگو بلافاصله ذخیره می‌شود.</p>
              {logoError && <p className="text-xs text-red-600">{logoError}</p>}
            </div>
          )}
        </div>
      </section>

      {canEdit && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-slate-600">افزودن بخش:</span>
          {SECTION_TYPES.map((type) => (
            <button
              key={type}
              type="button"
              disabled={locked || !canAddSection(state.sections, type)}
              onClick={() => addSection(type)}
              title={canAddSection(state.sections, type) ? undefined : "در هر مستند فقط یک بخش از این نوع مجاز است."}
              className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              + {SECTION_TYPE_LABELS[type]}
            </button>
          ))}
        </div>
      )}

      <div className="space-y-4">
        {state.sections.length === 0 && (
          <div className="rounded-lg border border-dashed border-slate-300 bg-white px-4 py-10 text-center text-sm text-slate-500">
            {canEdit ? "هنوز بخشی اضافه نشده است. از دکمه‌های بالا استفاده کنید." : "این مستند هنوز محتوایی ندارد."}
          </div>
        )}

        {state.sections.map((section, position) => {
          const index = position + 1;
          const common = { index, disabled: locked };
          return (
            <BlockFrame
              key={section.key}
              type={section.type}
              index={index}
              total={state.sections.length}
              disabled={locked}
              onMove={(direction) =>
                setState((current) =>
                  current ? { ...current, sections: moveSection(current.sections, position, direction) } : current,
                )
              }
              onRemove={() => {
                if (!window.confirm("این بخش حذف شود؟")) return;
                setState((current) =>
                  current ? { ...current, sections: current.sections.filter((s) => s.key !== section.key) } : current,
                );
              }}
            >
              {section.type === "Short Explanation" && (
                <ShortBlock section={section} {...common} update={(u) => updateSection(section.key, u)} />
              )}
              {section.type === "Long Explanation" && (
                <LongBlock
                  section={section}
                  {...common}
                  documentId={document.id}
                  trackUpload={trackUpload}
                  update={(u) => updateSection(section.key, u)}
                />
              )}
              {section.type === "Responsibilities" && (
                <ResponsibilitiesBlock section={section} {...common} update={(u) => updateSection(section.key, u)} />
              )}
              {section.type === "Changes Table" && (
                <ChangesBlock
                  section={section}
                  {...common}
                  previous={content.previous_changes}
                  revisionDisplay={document.revision_display}
                  update={(u) => updateSection(section.key, u)}
                />
              )}
              {section.type === "Attachment" && (
                <AttachmentBlock
                  section={section}
                  {...common}
                  documentId={document.id}
                  update={(u) => updateSection(section.key, u)}
                />
              )}
            </BlockFrame>
          );
        })}
      </div>

      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold text-slate-900">پاورقی</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <FieldLabel>متن آزاد</FieldLabel>
            <input
              type="text"
              value={state.footnote1}
              disabled={locked}
              maxLength={255}
              placeholder="مثال: واحد برنامه ریزی شرکت"
              onChange={(event) => setState({ ...state, footnote1: event.target.value })}
              className={inputClass}
            />
          </label>
          <label className="block">
            <FieldLabel>متن دلخواه</FieldLabel>
            <input
              type="text"
              value={state.footnote2}
              disabled={locked}
              maxLength={255}
              placeholder="محل تایپ متن دلخواه"
              onChange={(event) => setState({ ...state, footnote2: event.target.value })}
              className={inputClass}
            />
          </label>
        </div>
      </section>

      {/* Sticky inside the content column (not fixed to the window, which would
          slide it under the sidebar). The negative margins cancel <main>'s padding
          so the bar spans the column edge to edge. */}
      <div className="sticky bottom-0 z-40 -mx-8 -mb-8 mt-6 border-t border-slate-200 bg-white/95 px-8 py-3 backdrop-blur">
        <div className="mx-auto flex max-w-4xl flex-wrap items-center gap-3">
          {canEdit && (
            <button
              type="button"
              onClick={() => void save()}
              disabled={saveBlocked || !dirty}
              title={pendingUploads > 0 ? "تا پایان بارگذاری فایل‌ها صبر کنید." : undefined}
              className="rounded bg-purple-800 px-6 py-2 text-sm font-semibold text-white hover:bg-purple-900 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? "در حال ذخیره..." : "ذخیره"}
            </button>
          )}
          <button
            type="button"
            onClick={preview}
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
