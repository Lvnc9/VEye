"use client";

import { useEffect, useRef, useState, type PointerEvent } from "react";
import { ApiError } from "@/lib/api-client";
import { todayJalali } from "@/lib/jalali";
import { useCurrentUser } from "@/lib/current-user";
import { ErrorBanner } from "@/components/StatusBanner";

const PAD_WIDTH = 480;
const PAD_HEIGHT = 200;

interface Props {
  title: string;
  prompt: string;
  confirmLabel: string;
  /** Sends the signature. A rejection's message is shown in the dialog; a
   *  resolution closes it (the caller does that). */
  onSubmit: (image: Blob) => Promise<void>;
  onCancel: () => void;
}

/**
 * Sign-off dialog with a signature pad (V_1.0's Tk canvas, which it then
 * screen-grabbed). Name, سمت and date are shown but not editable and are not
 * sent: the server records the signed-in user's own.
 */
export function SignatureDialog({ title, prompt, confirmLabel, onSubmit, onCancel }: Props) {
  const { user } = useCurrentUser();
  const dialogRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const last = useRef<{ x: number; y: number } | null>(null);
  const [hasInk, setHasInk] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Paint the pad white (the exported PNG is opaque) at the screen's pixel density.
  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context) return;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = PAD_WIDTH * ratio;
    canvas.height = PAD_HEIGHT * ratio;
    context.scale(ratio, ratio);
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, PAD_WIDTH, PAD_HEIGHT);
    context.lineWidth = 2.5;
    context.lineCap = "round";
    context.lineJoin = "round";
    context.strokeStyle = "#0f172a";
    dialogRef.current?.focus();
  }, []);

  function point(event: PointerEvent<HTMLCanvasElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    return {
      x: ((event.clientX - rect.left) / rect.width) * PAD_WIDTH,
      y: ((event.clientY - rect.top) / rect.height) * PAD_HEIGHT,
    };
  }

  function start(event: PointerEvent<HTMLCanvasElement>) {
    const context = event.currentTarget.getContext("2d");
    if (!context || sending) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    const p = point(event);
    last.current = p;
    // A tap leaves a dot, so it is not silently ignored.
    context.beginPath();
    context.moveTo(p.x, p.y);
    context.lineTo(p.x + 0.01, p.y);
    context.stroke();
    setHasInk(true);
  }

  function move(event: PointerEvent<HTMLCanvasElement>) {
    const from = last.current;
    const context = event.currentTarget.getContext("2d");
    if (!from || !context) return;
    const p = point(event);
    context.beginPath();
    context.moveTo(from.x, from.y);
    context.lineTo(p.x, p.y);
    context.stroke();
    last.current = p;
  }

  function stop() {
    last.current = null;
  }

  function clear() {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!context) return;
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, PAD_WIDTH, PAD_HEIGHT);
    setHasInk(false);
    setError(null);
  }

  async function submit() {
    const canvas = canvasRef.current;
    if (!canvas || !hasInk) return;
    setSending(true);
    setError(null);
    try {
      const image = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
      if (!image) throw new Error("export failed");
      await onSubmit(image);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ثبت امضا ممکن نشد. دوباره تلاش کنید.");
      setSending(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/50 p-4 pt-16"
      onKeyDown={(event) => event.key === "Escape" && !sending && onCancel()}
      onClick={(event) => event.target === event.currentTarget && !sending && onCancel()}
    >
      <div
        ref={dialogRef}
        tabIndex={-1}
        className="w-full max-w-lg space-y-4 rounded-lg bg-white p-5 shadow-xl outline-none"
      >
        <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
        <p className="text-sm leading-6 text-slate-600">{prompt}</p>

        <dl className="grid grid-cols-3 gap-3 rounded border border-slate-200 bg-slate-50 p-3 text-sm">
          <div>
            <dt className="text-xs text-slate-500">نام و نام خانوادگی</dt>
            <dd className="font-medium text-slate-900">{user?.full_name ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">سمت</dt>
            <dd className="font-medium text-slate-900">{user?.title ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">تاریخ</dt>
            <dd className="font-medium text-slate-900">{todayJalali()}</dd>
          </div>
        </dl>

        <div>
          <div className="mb-1 flex items-center justify-between text-sm">
            <span className="font-medium text-slate-700">امضا</span>
            <button
              type="button"
              onClick={clear}
              disabled={!hasInk || sending}
              className="text-slate-500 underline hover:text-slate-800 disabled:opacity-40"
            >
              پاک کردن
            </button>
          </div>
          <canvas
            ref={canvasRef}
            aria-label="محل امضا"
            style={{ width: "100%", maxWidth: PAD_WIDTH, aspectRatio: `${PAD_WIDTH} / ${PAD_HEIGHT}`, touchAction: "none" }}
            className="cursor-crosshair rounded border border-slate-300 bg-white"
            onPointerDown={start}
            onPointerMove={move}
            onPointerUp={stop}
            onPointerCancel={stop}
          />
          {!hasInk && <p className="mt-1 text-xs text-slate-500">با ماوس یا انگشت در کادر بالا امضا کنید.</p>}
        </div>

        {error && <ErrorBanner message={error} />}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={sending}
            className="rounded border border-slate-300 bg-white px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            انصراف
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={!hasInk || sending}
            className="rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {sending ? "در حال ثبت..." : `ثبت امضا و ${confirmLabel}`}
          </button>
        </div>
      </div>
    </div>
  );
}
