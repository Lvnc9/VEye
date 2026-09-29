"use client";

import { useCallback, useEffect, useReducer, useState, type Reducer, type SetStateAction } from "react";
import { useRouter } from "next/navigation";
import { ApiError, apiGet, apiPut } from "@/lib/api-client";
import { PdfBuildError, buildPdf, openPdfInTab } from "@/lib/pdf";
import { setFlash } from "@/lib/flash";
import { useCurrentUser } from "@/lib/current-user";
import type { ContentResponse } from "@/lib/types";
import { emptyHistory, record, redo, undo, type History } from "@/lib/undo-history";
import { clearDraft, findRecovery, writeDraft, type Recovery } from "@/lib/designer-draft";

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
  /** Fresh React keys, for work restored from this browser after a reload. */
  rekey(state: S): S;
}

/** How long typing must pause before unsaved work is written to this browser. */
const DRAFT_DEBOUNCE_MS = 1000;

type Model<S> = { state: S; history: History<S> };

type Action<S> =
  | { type: "edit"; action: SetStateAction<S>; at: number }
  | { type: "replace"; state: S; keepHistory: boolean }
  | { type: "undo" }
  | { type: "redo" };

/** The editable state and its undo history, moved together so undo stays pure. */
function modelReducer<S>(model: Model<S>, action: Action<S>): Model<S> {
  switch (action.type) {
    case "edit": {
      const next = typeof action.action === "function" ? (action.action as (current: S) => S)(model.state) : action.action;
      if (Object.is(next, model.state)) return model;
      return { state: next, history: record(model.history, model.state, action.at) };
    }
    case "replace":
      return { state: action.state, history: action.keepHistory ? model.history : emptyHistory() };
    case "undo": {
      const step = undo(model.history, model.state);
      return step ? { state: step.state, history: step.history } : model;
    }
    case "redo": {
      const step = redo(model.history, model.state);
      return step ? { state: step.state, history: step.history } : model;
    }
  }
}

/** The load / save / preview life cycle of `/documents/{id}/content/`. */
export function useDesignerDocument<S>(initial: ContentResponse, adapter: DesignerAdapter<S>) {
  const router = useRouter();
  const { can, user } = useCurrentUser();
  const id = initial.document.id;

  const [content, setContent] = useState<ContentResponse>(initial);
  const [model, dispatch] = useReducer(modelReducer as Reducer<Model<S>, Action<S>>, undefined, () => ({
    state: adapter.fromResponse(initial),
    history: emptyHistory<S>(),
  }));
  const state = model.state;
  /** Every edit goes through here, so it can be undone (Ctrl/⌘+Z). */
  const setState = useCallback((action: SetStateAction<S>) => dispatch({ type: "edit", action, at: Date.now() }), []);
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
      dispatch({ type: "replace", state: next, keepHistory: false });
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

  // Unsaved work survives a closed tab (lib/designer-draft.ts). Once the signed-in user
  // is known, look for work left from before; adjusting state during render is React's
  // pattern for deriving it from a value that arrives later (no effect needed).
  const userId = user?.id ?? null;
  const [recoveryFor, setRecoveryFor] = useState<number | null>(null);
  const [recovery, setRecovery] = useState<Recovery<S>>(null);
  if (userId !== null && recoveryFor !== userId) {
    setRecoveryFor(userId);
    setRecovery(findRecovery<S>(userId, id, content.version, savedSnapshot, adapter.snapshot));
  }
  const offering = recovery?.kind === "offer";
  const stateSnapshot = adapter.snapshot(state);

  useEffect(() => {
    // Until the author answers the offer, the stored work is left as it is.
    if (userId === null || offering || !canEdit) return;
    if (!dirty) {
      clearDraft(userId, id);
      return;
    }
    const timer = window.setTimeout(
      () => writeDraft({ userId, documentId: id, baseVersion: content.version, state, at: Date.now() }),
      DRAFT_DEBOUNCE_MS,
    );
    return () => window.clearTimeout(timer);
    // `state` is written as of the latest snapshot; the snapshot string is the trigger.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, id, offering, canEdit, dirty, stateSnapshot, content.version]);

  function restoreDraft() {
    if (recovery?.kind !== "offer") return;
    setState(adapter.rekey(recovery.state));
    setRecovery(null);
  }

  function discardDraft() {
    if (userId !== null) clearDraft(userId, id);
    setRecovery(null);
  }

  // Ctrl/⌘+Z undoes, Ctrl/⌘+Shift+Z or Ctrl+Y redoes — for the whole document, text
  // fields included. Matched on the physical key: with a Persian layout `key` is «ظ».
  useEffect(() => {
    if (locked) return;
    const onKey = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || event.altKey) return;
      // The rich editor keeps its own history for typing; the document's undo is for everything else.
      if (event.target instanceof Element && event.target.closest(".rich-editor")) return;
      if (event.code === "KeyZ" && !event.shiftKey) dispatch({ type: "undo" });
      else if ((event.code === "KeyZ" && event.shiftKey) || event.code === "KeyY") dispatch({ type: "redo" });
      else return;
      event.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [locked]);

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

  /**
   * Saves the body. Since Phase 12 (the owner's decision, 2026-09-28) the page
   * stays open — the live paper is beside the editor; `andReturn` goes back to
   * «ساخت مستند» afterwards, as V_1.0 always did (poster_01.py show_pdf →
   * change_to_documents1).
   */
  async function save({ andReturn = false }: { andReturn?: boolean } = {}) {
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
      // Saving is not a step: what came back equals what was sent, and earlier steps stay undoable.
      dispatch({ type: "replace", state: next, keepHistory: true });
      setSavedSnapshot(adapter.snapshot(next));
      const message = `مستند ${response.document.full_code} ذخیره شد.`;
      if (andReturn) {
        setFlash(message); // the register shows it
        router.push("/documents");
      } else {
        setNotice(message);
      }
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
    undo: () => dispatch({ type: "undo" }),
    redo: () => dispatch({ type: "redo" }),
    canUndo: model.history.past.length > 0,
    recovery,
    restoreDraft,
    discardDraft,
    canRedo: model.history.future.length > 0,
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
