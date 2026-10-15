"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api-client";
import { REASON_MAX_LENGTH, validateWithdrawNote } from "@/lib/workflow";
import { ErrorBanner } from "@/components/StatusBanner";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogFooter } from "@/components/ui/Dialog";
import { textareaClass } from "@/components/ui/Field";

interface Props {
  code: string;
  onSubmit: (note: string) => Promise<void>;
  onCancel: () => void;
}

/** «بازپس‌گیری» (Phase 20): the submitter takes the document back to draft before تصویب. Like مرجوع the
 *  signatures are cleared; unlike it the note is optional — it is their own document. */
export function WithdrawDialog({ code, onSubmit, onCancel }: Props) {
  const box = useRef<HTMLTextAreaElement>(null);
  const [note, setNote] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    box.current?.focus();
  }, []);

  async function submit() {
    const problem = validateWithdrawNote(note);
    if (problem) {
      setError(problem);
      return;
    }
    setSending(true);
    setError(null);
    try {
      await onSubmit(note);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "بازپس‌گیری ممکن نشد. دوباره تلاش کنید.");
      setSending(false);
    }
  }

  return (
    <Dialog label="بازپس‌گیری مستند" title={`بازپس‌گیری مستند ${code}`} onClose={onCancel} busy={sending}>
      <p className="text-sm leading-7 text-slate-600">
        مستند به پیش‌نویس برمی‌گردد و همهٔ امضاها پاک می‌شوند. پس از اصلاح، دوباره آن را برای تایید ارسال کنید. کسانی
        که منتظر اقدام روی آن بودند باخبر می‌شوند.
      </p>
      <label className="block text-sm">
        <span className="mb-1.5 block text-slate-700">
          توضیح <span className="text-slate-400">(اختیاری)</span>
        </span>
        <textarea
          ref={box}
          value={note}
          maxLength={REASON_MAX_LENGTH}
          rows={3}
          onChange={(event) => setNote(event.target.value)}
          className={textareaClass}
        />
      </label>
      {error && <ErrorBanner message={error} />}
      <DialogFooter>
        <Button onClick={onCancel} disabled={sending}>
          انصراف
        </Button>
        <Button variant="primary" onClick={submit} loading={sending}>
          {sending ? "در حال ثبت..." : "بازپس‌گیری"}
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
