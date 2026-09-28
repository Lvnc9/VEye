"use client";

import { useEffect, useRef, useState, type PointerEvent } from "react";
import { ApiError } from "@/lib/api-client";
import { todayJalali } from "@/lib/jalali";
import { useCurrentUser } from "@/lib/current-user";
import { Eraser, PenLine } from "lucide-react";
import { ErrorBanner } from "@/components/StatusBanner";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogFooter } from "@/components/ui/Dialog";

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
    <Dialog label={title} title={title} onClose={onCancel} busy={sending}>
      <p className="text-sm leading-7 text-slate-600">{prompt}</p>

      <dl className="grid grid-cols-3 gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm">
        <div className="min-w-0">
          <dt className="text-xs text-slate-500">نام و نام خانوادگی</dt>
          <dd className="truncate font-bold text-slate-900">{user?.full_name ?? "—"}</dd>
        </div>
        <div className="min-w-0">
          <dt className="text-xs text-slate-500">سمت</dt>
          <dd className="truncate font-bold text-slate-900">{user?.title ?? "—"}</dd>
        </div>
        <div className="min-w-0">
          <dt className="text-xs text-slate-500">تاریخ</dt>
          <dd className="font-bold text-slate-900">{todayJalali()}</dd>
        </div>
      </dl>

      <div>
        <div className="mb-1.5 flex items-center justify-between text-sm">
          <span className="flex items-center gap-1.5 text-slate-700">
            <PenLine className="size-4 text-slate-400" />
            امضا
          </span>
          <Button variant="ghost" size="xs" icon={<Eraser />} onClick={clear} disabled={!hasInk || sending}>
            پاک کردن
          </Button>
        </div>
        <canvas
          ref={canvasRef}
          aria-label="محل امضا"
          style={{ width: "100%", maxWidth: PAD_WIDTH, aspectRatio: `${PAD_WIDTH} / ${PAD_HEIGHT}`, touchAction: "none" }}
          className={`cursor-crosshair rounded-xl border border-dashed bg-white transition-colors duration-200 ${
            hasInk ? "border-brand-300" : "border-slate-300 hover:border-slate-400"
          }`}
          onPointerDown={start}
          onPointerMove={move}
          onPointerUp={stop}
          onPointerCancel={stop}
        />
        {!hasInk && <p className="mt-1.5 text-xs text-slate-500">با ماوس یا انگشت در کادر بالا امضا کنید.</p>}
      </div>

      {error && <ErrorBanner message={error} />}

      <DialogFooter>
        <Button onClick={onCancel} disabled={sending}>
          انصراف
        </Button>
        <Button variant="primary" onClick={submit} disabled={!hasInk} loading={sending}>
          {sending ? "در حال ثبت..." : `ثبت امضا و ${confirmLabel}`}
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
