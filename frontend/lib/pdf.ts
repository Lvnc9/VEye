/**
 * Building and opening a document's PDF (Phase 4).
 *
 * A build is an explicit action: POST queues a Celery task and returns at once,
 * then the state is polled until it leaves "building". The register list never
 * renders anything — it only reads `pdf_status` from the row.
 */
import { ApiError, apiGet, apiPost } from "./api-client";
import type { PdfKind, PdfState, PdfStatus } from "./types";

export const PDF_POLL_INTERVAL_MS = 1000;
// Longer than the worker's hard limit (300 s) never helps; a slow document is
// still ready long before this and the user can simply reopen the register.
export const PDF_POLL_TIMEOUT_MS = 180_000;

export const MESSAGES = {
  timeout: "ساخت PDF بیش از حد طول کشید. کمی بعد دوباره بررسی کنید.",
  failed: "ساخت PDF ناموفق بود. دوباره تلاش کنید.",
  noDownload: "فایل PDF در دسترس نیست.",
  building: "در حال آماده‌سازی PDF…",
} as const;

export class PdfBuildError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PdfBuildError";
  }
}

const statePath = (documentId: number, kind: PdfKind) => `/documents/${documentId}/pdf/${kind}/`;

export function readPdfState(documentId: number, kind: PdfKind): Promise<PdfState> {
  return apiGet<PdfState>(statePath(documentId, kind));
}

/** What the چاپ button of a finalized row does, from the official PDF's status. */
export function officialPdfAction(status: PdfStatus): {
  mode: "build" | "open" | "busy";
  label: string;
} {
  switch (status) {
    case "ready":
      return { mode: "open", label: "چاپ" };
    case "building":
      return { mode: "busy", label: "در حال ساخت…" };
    case "failed":
      return { mode: "build", label: "ساخت مجدد PDF" };
    default:
      return { mode: "build", label: "ساخت PDF" };
  }
}

interface WaitOptions {
  intervalMs?: number;
  timeoutMs?: number;
  /** Injected for tests. */
  sleep?: (ms: number) => Promise<void>;
  now?: () => number;
}

/** Poll `read` until the build leaves "building". Rejects with a PdfBuildError
 *  if it is still running at the deadline. */
export async function waitForPdf(
  read: () => Promise<PdfState>,
  {
    intervalMs = PDF_POLL_INTERVAL_MS,
    timeoutMs = PDF_POLL_TIMEOUT_MS,
    sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
    now = Date.now,
  }: WaitOptions = {},
): Promise<PdfState> {
  const deadline = now() + timeoutMs;
  for (;;) {
    const state = await read();
    if (state.status !== "building") return state;
    if (now() >= deadline) throw new PdfBuildError(MESSAGES.timeout);
    await sleep(intervalMs);
  }
}

/** Ask for a build and wait for its result. A second click (or another user's)
 *  while a build is running is not an error — it just joins that build. */
export async function buildPdf(
  documentId: number,
  kind: PdfKind,
  options?: WaitOptions,
): Promise<PdfState> {
  try {
    await apiPost<PdfState>(statePath(documentId, kind));
  } catch (err) {
    const code = err instanceof ApiError ? (err.data as { code?: string } | undefined)?.code : undefined;
    if (code !== "build_in_progress") throw err;
  }
  const state = await waitForPdf(() => readPdfState(documentId, kind), options);
  if (state.status === "failed") throw new PdfBuildError(state.error || MESSAGES.failed);
  return state;
}

/** Follow a build somebody already started (a row that loads as "building"). */
export function followPdf(documentId: number, kind: PdfKind, options?: WaitOptions): Promise<PdfState> {
  return waitForPdf(() => readPdfState(documentId, kind), options);
}

/**
 * Open a PDF in a new tab from inside a click handler.
 *
 * The tab has to be opened *synchronously* — browsers block a window opened
 * after an await — so a placeholder goes up first and is pointed at the file
 * once `produce` resolves. `produce` also serves to refresh the session before
 * the tab makes its own (cookie-only) request for the file.
 */
export async function openPdfInTab(produce: () => Promise<PdfState>): Promise<void> {
  const tab = window.open("", "_blank");
  if (tab) {
    tab.opener = null;
    tab.document.title = MESSAGES.building;
    tab.document.body.innerHTML = "";
    const note = tab.document.createElement("p");
    note.textContent = MESSAGES.building;
    note.setAttribute("dir", "rtl");
    note.style.fontFamily = "sans-serif";
    tab.document.body.appendChild(note);
  }
  try {
    const state = await produce();
    if (!state.download_url) throw new PdfBuildError(MESSAGES.noDownload);
    if (tab) tab.location.href = state.download_url;
    else window.open(state.download_url, "_blank");
  } catch (err) {
    tab?.close();
    throw err;
  }
}
