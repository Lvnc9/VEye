"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError, apiPost } from "@/lib/api-client";
import { PageCache, type PreviewResponse, type ShownPage } from "@/lib/live-paper";

/** Pause in typing before the paper is redrawn. */
const DEBOUNCE_MS = 800;

type Status = { state: "idle" } | { state: "updating" } | { state: "error"; message: string };

/**
 * The live paper (Phase 12): the document's pages exactly as they print,
 * redrawn by the server's own renderer shortly after each change. `body` is the
 * unsaved content (a content PUT's JSON) or null to show what is stored — for a
 * reviewer, a finished document, or while nothing has changed.
 */
export function LivePaper({
  documentId,
  body,
  refreshKey = "",
}: {
  documentId: number;
  body: object | null;
  /** Changes that are saved outright (the logo) and so are not in `body`. */
  refreshKey?: string;
}) {
  const key = useMemo(() => JSON.stringify({ body, refreshKey }), [body, refreshKey]);
  const cache = useRef(new PageCache());
  const [pages, setPages] = useState<ShownPage[]>([]);
  const [meta, setMeta] = useState<{ count: number; truncated: boolean }>({ count: 0, truncated: false });
  const [status, setStatus] = useState<Status>({ state: "updating" });
  const [zoom, setZoom] = useState<"fit" | "print">("fit");
  /** Until the first pages arrive, draw at once; afterwards wait for a pause in typing. */
  const drawn = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    const payload = (JSON.parse(key) as { body: object | null }).body;

    async function draw(known: string[]): Promise<void> {
      const response = await apiPost<PreviewResponse>(
        `/documents/${documentId}/live-preview/`,
        { ...(payload ? { body: payload } : {}), known_hashes: known },
        { signal: controller.signal },
      );
      const shown = cache.current.resolve(response.pages);
      if (shown === null) {
        // A page came without its image and it is no longer cached: ask again for everything.
        if (known.length) return draw([]);
        throw new Error("missing page");
      }
      drawn.current = true;
      setPages(shown);
      setMeta({ count: response.page_count, truncated: response.truncated });
      setStatus({ state: "idle" });
    }

    const delay = drawn.current ? DEBOUNCE_MS : 0;
    const timer = window.setTimeout(() => {
      setStatus({ state: "updating" });
      draw(cache.current.hashes).catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setStatus({
          state: "error",
          message:
            err instanceof ApiError
              ? err.message
              : "به‌روزرسانی پیش‌نمایش ممکن نشد؛ با تغییر بعدی دوباره تلاش می‌شود.",
        });
      });
    }, delay);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [documentId, key]);

  return (
    <section aria-label="پیش‌نمایش چاپ" className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <header className="flex flex-wrap items-center gap-2 border-b border-slate-200 px-4 py-2.5">
        <h2 className="text-sm font-semibold text-slate-900">پیش‌نمایش چاپ</h2>
        <span aria-live="polite" className="text-xs text-slate-500">
          {status.state === "updating" ? "در حال به‌روزرسانی…" : status.state === "idle" && meta.count ? `${meta.count.toLocaleString("fa-IR")} صفحه` : ""}
        </span>
        <div className="ms-auto flex overflow-hidden rounded border border-slate-300 text-xs">
          {(
            [
              ["fit", "هم‌عرض ستون"],
              ["print", "اندازهٔ چاپ"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              aria-pressed={zoom === value}
              onClick={() => setZoom(value)}
              className={`px-2.5 py-1 ${zoom === value ? "bg-slate-800 text-white" : "bg-white text-slate-600 hover:bg-slate-50"}`}
            >
              {label}
            </button>
          ))}
        </div>
      </header>

      {status.state === "error" && (
        <p role="status" className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800">
          {status.message}
        </p>
      )}

      <div className="relative overflow-auto bg-slate-100 p-3" style={{ maxHeight: "calc(100vh - 12rem)" }}>
        {pages.length === 0 && status.state === "updating" && (
          <p className="py-16 text-center text-sm text-slate-500">در حال آماده‌سازی صفحه‌ها…</p>
        )}
        <div className={`space-y-4 transition-opacity ${status.state === "updating" && pages.length ? "opacity-70" : ""}`}>
          {pages.map((page, index) => (
            <figure key={`${index}-${page.hash}`} className="mx-auto" style={zoom === "print" ? { width: 794 } : undefined}>
              {/* eslint-disable-next-line @next/next/no-img-element -- a data URL drawn by the server, not a static asset */}
              <img
                src={page.src}
                alt={`صفحهٔ ${(index + 1).toLocaleString("fa-IR")}`}
                className="block w-full bg-white shadow-md"
                draggable={false}
              />
              <figcaption className="mt-1 text-center text-xs text-slate-500">
                صفحه {(index + 1).toLocaleString("fa-IR")} از {meta.count.toLocaleString("fa-IR")}
              </figcaption>
            </figure>
          ))}
        </div>
        {meta.truncated && (
          <p className="mt-3 text-center text-xs text-slate-500">
            فقط {pages.length.toLocaleString("fa-IR")} صفحهٔ نخست نمایش داده می‌شود؛ برای همهٔ صفحه‌ها «نمایش» را بزنید.
          </p>
        )}
      </div>
    </section>
  );
}
