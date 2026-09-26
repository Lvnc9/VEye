"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, apiGet, apiPut } from "@/lib/api-client";
import { PdfBuildError, buildPdf, openPdfInTab } from "@/lib/pdf";
import { setFlash } from "@/lib/flash";
import { useCurrentUser } from "@/lib/current-user";
import type { ContentResponse } from "@/lib/types";

/** How one kind of document body becomes editable state and back. The classic
 *  block designer and the form designer each supply one; everything else about
 *  loading, saving and conflicts is shared. */
export interface DesignerAdapter<S> {
  /** After a save, `previous` is the state that was just sent, so its React keys survive. */
  fromResponse(response: ContentResponse, previous?: S): S;
  toPayload(state: S): object;
  /** "Has anything changed since the last save?" */
  snapshot(state: S): string;
  /** Local checks that mirror the server's; Persian messages. */
  validate(state: S): string[];
}

/** The load / save / preview life cycle of `/documents/{id}/content/`. */
export function useDesignerDocument<S>(initial: ContentResponse, adapter: DesignerAdapter<S>) {
  const router = useRouter();
  const { can } = useCurrentUser();
  const id = initial.document.id;

  const [content, setContent] = useState<ContentResponse>(initial);
  const [state, setState] = useState<S>(() => adapter.fromResponse(initial));
  const [savedSnapshot, setSavedSnapshot] = useState(() => adapter.snapshot(adapter.fromResponse(initial)));
  const [reloading, setReloading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [saving, setSaving] = useState(false);
  const [saveErrors, setSaveErrors] = useState<string[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  const [pendingUploads, setPendingUploads] = useState(0);
  const [previewing, setPreviewing] = useState(false);

  const applyResponse = useCallback(
    (response: ContentResponse) => {
      const next = adapter.fromResponse(response);
      setContent(response);
      setState(next);
      setSavedSnapshot(adapter.snapshot(next));
      setConflict(false);
      setLoadError(null);
    },
    [adapter],
  );

  /** Re-fetch on demand (after a version conflict, or if the document was locked
   *  while we edited). Called from event handlers, so it may set state freely. */
  const reload = useCallback(async () => {
    setReloading(true);
    try {
      applyResponse(await apiGet<ContentResponse>(`/documents/${id}/content/`));
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "دریافت مستند ممکن نشد.");
    } finally {
      setReloading(false);
    }
  }, [id, applyResponse]);

  const dirty = adapter.snapshot(state) !== savedSnapshot;
  const canEdit = content.editable && can("create_document");
  /** Every input is disabled while this is true. */
  const locked = !canEdit || saving;

  // Closing the tab with unsaved work is the one way to lose it silently.
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  // نمایش: a watermarked preview of what was last *saved* (the server renders the
  // stored document), so it is held while there are unsaved edits.
  function preview() {
    setSaveErrors([]);
    setPreviewing(true);
    openPdfInTab(() => buildPdf(id, "preview"))
      .catch((err) =>
        setSaveErrors([
          err instanceof ApiError || err instanceof PdfBuildError ? err.message : "ساخت پیش‌نمایش ممکن نشد.",
        ]),
      )
      .finally(() => setPreviewing(false));
  }

  const trackUpload = useCallback(() => {
    setPendingUploads((n) => n + 1);
    return () => setPendingUploads((n) => n - 1);
  }, []);

  async function save() {
    const problems = adapter.validate(state);
    if (problems.length > 0) {
      setSaveErrors(problems);
      return;
    }

    setSaving(true);
    setSaveErrors([]);
    setNotice(null);
    try {
      const response = await apiPut<ContentResponse>(`/documents/${id}/content/`, adapter.toPayload(state));
      // Hand back the state just sent so each block keeps its React key.
      const next = adapter.fromResponse(response, state);
      setContent(response);
      setState(next);
      setSavedSnapshot(adapter.snapshot(next));
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

  return {
    content,
    setContent,
    state,
    setState,
    dirty,
    canEdit,
    locked,
    reloading,
    loadError,
    saving,
    saveErrors,
    notice,
    setNotice,
    conflict,
    reload,
    save,
    preview,
    previewing,
    pendingUploads,
    trackUpload,
  };
}

export type DesignerDocument<S> = ReturnType<typeof useDesignerDocument<S>>;
