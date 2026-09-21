"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api-client";
import { ErrorBanner } from "@/components/StatusBanner";

interface Props {
  title: string;
  message: string;
  confirmLabel: string;
  /** Destructive actions are red; everything else uses the neutral colour. */
  danger?: boolean;
  onConfirm: () => Promise<void>;
  onCancel: () => void;
}

/** A yes/no question before something that cannot be undone. Same shape as ReturnDialog: Escape and
 *  the backdrop cancel, and the parent closes it once `onConfirm` resolves. */
export function ConfirmDialog({ title, message, confirmLabel, danger = false, onConfirm, onCancel }: Props) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    cancelRef.current?.focus();
  }, []);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "انجام نشد. دوباره تلاش کنید.");
      setBusy(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/50 p-4 pt-24"
      onKeyDown={(event) => event.key === "Escape" && !busy && onCancel()}
      onClick={(event) => event.target === event.currentTarget && !busy && onCancel()}
    >
      <div className="w-full max-w-md space-y-4 rounded-lg bg-white p-5 shadow-xl">
        <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
        <p className="text-sm leading-6 text-slate-600">{message}</p>
        {error && <ErrorBanner message={error} />}
        <div className="flex justify-end gap-2">
          <button
            ref={cancelRef}
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="rounded border border-slate-300 bg-white px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            انصراف
          </button>
          <button
            type="button"
            onClick={confirm}
            disabled={busy}
            className={`rounded px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 ${
              danger ? "bg-red-600 hover:bg-red-700" : "bg-slate-900 hover:bg-slate-700"
            }`}
          >
            {busy ? "لحظه‌ای صبر کنید..." : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
