"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api-client";
import { REASON_MAX_LENGTH, validateReason } from "@/lib/workflow";
import { ErrorBanner } from "@/components/StatusBanner";

interface Props {
  code: string;
  onSubmit: (reason: string) => Promise<void>;
  onCancel: () => void;
}

/** مرجوع: the reviewer sends the document back to draft. A reason is mandatory —
 *  it is what the author reads, and it goes into the audit trail. */
export function ReturnDialog({ code, onSubmit, onCancel }: Props) {
  const box = useRef<HTMLTextAreaElement>(null);
  const [reason, setReason] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    box.current?.focus();
  }, []);

  async function submit() {
    const problem = validateReason(reason);
    if (problem) {
      setError(problem);
      return;
    }
    setSending(true);
    setError(null);
    try {
      await onSubmit(reason);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "مرجوع کردن ممکن نشد. دوباره تلاش کنید.");
      setSending(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="مرجوع کردن مستند"
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/50 p-4 pt-24"
      onKeyDown={(event) => event.key === "Escape" && !sending && onCancel()}
      onClick={(event) => event.target === event.currentTarget && !sending && onCancel()}
    >
      <div className="w-full max-w-lg space-y-4 rounded-lg bg-white p-5 shadow-xl">
        <h2 className="text-lg font-semibold text-slate-900">مرجوع کردن مستند {code}</h2>
        <p className="text-sm leading-6 text-slate-600">
          مستند به پیش‌نویس بازمی‌گردد، همهٔ امضاها پاک می‌شوند و تدوین‌کننده باید پس از اصلاح، آن را دوباره برای تایید
          ارسال کند. دلیل شما در سوابق مستند ثبت می‌شود.
        </p>
        <label className="block text-sm">
          <span className="mb-1 block font-medium text-slate-700">دلیل مرجوع کردن</span>
          <textarea
            ref={box}
            value={reason}
            maxLength={REASON_MAX_LENGTH}
            rows={4}
            onChange={(event) => setReason(event.target.value)}
            className="w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm"
          />
        </label>
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
            disabled={sending}
            className="rounded bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50"
          >
            {sending ? "در حال ثبت..." : "مرجوع کردن"}
          </button>
        </div>
      </div>
    </div>
  );
}
