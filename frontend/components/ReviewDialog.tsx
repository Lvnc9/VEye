"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api-client";
import { REVIEW_NOTE_MAX_LENGTH, reviewIntervalLabel } from "@/lib/review";
import { ErrorBanner } from "@/components/StatusBanner";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogFooter } from "@/components/ui/Dialog";
import { textareaClass } from "@/components/ui/Field";

interface Props {
  code: string;
  intervalMonths: number;
  onSubmit: (note: string) => Promise<void>;
  onCancel: () => void;
}

/** «بازنگری شد — بدون تغییر» (Phase 21): an author looked at a document in force and found nothing to change.
 *  It goes into the document's trail with the optional note, and the review clock starts again. */
export function ReviewDialog({ code, intervalMonths, onSubmit, onCancel }: Props) {
  const box = useRef<HTMLTextAreaElement>(null);
  const [note, setNote] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    box.current?.focus();
  }, []);

  async function submit() {
    if (note.trim().length > REVIEW_NOTE_MAX_LENGTH) {
      setError(`توضیح نباید بیش از ${REVIEW_NOTE_MAX_LENGTH.toLocaleString("fa-IR")} نویسه باشد.`);
      return;
    }
    setSending(true);
    setError(null);
    try {
      await onSubmit(note);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ثبت بازنگری ممکن نشد. دوباره تلاش کنید.");
      setSending(false);
    }
  }

  return (
    <Dialog label="ثبت بازنگری دوره‌ای" title={`بازنگری دوره‌ای ${code}`} onClose={onCancel} busy={sending}>
      <p className="text-sm leading-7 text-soft-foreground">
        مستند را مرور کرده‌اید و تغییری لازم نیست. این بازنگری در سوابق مستند ثبت می‌شود و موعد بازنگری بعدی{" "}
        {intervalMonths > 0 ? `${reviewIntervalLabel(intervalMonths)} پس از امروز` : "تعیین نمی‌شود"} خواهد بود. اگر
        تغییری لازم است، به‌جای این کار «بازنگری جدید» بسازید.
      </p>
      <label className="block text-sm">
        <span className="mb-1.5 block text-soft-foreground">
          توضیح <span className="text-muted-foreground">(اختیاری)</span>
        </span>
        <textarea
          ref={box}
          value={note}
          maxLength={REVIEW_NOTE_MAX_LENGTH}
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
          {sending ? "در حال ثبت..." : "ثبت بازنگری بدون تغییر"}
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
