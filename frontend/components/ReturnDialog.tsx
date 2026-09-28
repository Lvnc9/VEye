"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api-client";
import { REASON_MAX_LENGTH, validateReason } from "@/lib/workflow";
import { ErrorBanner } from "@/components/StatusBanner";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogFooter } from "@/components/ui/Dialog";
import { textareaClass } from "@/components/ui/Field";

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
    <Dialog label="مرجوع کردن مستند" title={`مرجوع کردن مستند ${code}`} onClose={onCancel} busy={sending}>
      <p className="text-sm leading-7 text-slate-600">
        مستند به پیش‌نویس بازمی‌گردد، همهٔ امضاها پاک می‌شوند و تدوین‌کننده باید پس از اصلاح، آن را دوباره برای تایید
        ارسال کند. دلیل شما در سوابق مستند ثبت می‌شود.
      </p>
      <label className="block text-sm">
        <span className="mb-1.5 block text-slate-700">دلیل مرجوع کردن</span>
        <textarea
          ref={box}
          value={reason}
          maxLength={REASON_MAX_LENGTH}
          rows={4}
          onChange={(event) => setReason(event.target.value)}
          className={textareaClass}
        />
      </label>
      {error && <ErrorBanner message={error} />}
      <DialogFooter>
        <Button onClick={onCancel} disabled={sending}>
          انصراف
        </Button>
        <Button variant="danger" onClick={submit} loading={sending}>
          {sending ? "در حال ثبت..." : "مرجوع کردن"}
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
