"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { ApiError } from "@/lib/api-client";
import { TEXT_MAX } from "@/lib/quality";
import { ErrorBanner } from "@/components/StatusBanner";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogFooter } from "@/components/ui/Dialog";
import { textareaClass } from "@/components/ui/Field";

/**
 * Ask for one piece of text, then do something with it: a reason for rejecting or reopening, a root
 * cause, an effectiveness note. The same shape as `ReturnDialog` (Escape and the backdrop cancel, the
 * parent closes it once `onSubmit` resolves, a failure from the server stays in the dialog), made generic
 * so every quality decision that needs words is one component instead of six copies.
 *
 * `required` text is checked before the request; the server re-checks everything.
 */
export function TextDialog({
  title,
  description,
  fieldLabel,
  confirmLabel,
  danger = false,
  required = true,
  extra,
  onSubmit,
  onCancel,
}: {
  title: string;
  description?: string;
  fieldLabel: string;
  confirmLabel: string;
  danger?: boolean;
  required?: boolean;
  /** Anything else the decision needs beside the text (a severity select, say). */
  extra?: ReactNode;
  onSubmit: (text: string) => Promise<void>;
  onCancel: () => void;
}) {
  const box = useRef<HTMLTextAreaElement>(null);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    box.current?.focus();
  }, []);

  async function submit() {
    if (required && !text.trim()) {
      setError(`${fieldLabel} را بنویسید.`);
      return;
    }
    setSending(true);
    setError(null);
    try {
      await onSubmit(text.trim());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "انجام نشد. دوباره تلاش کنید.");
      setSending(false);
    }
  }

  return (
    <Dialog label={title} title={title} onClose={onCancel} busy={sending}>
      {description && <p className="text-sm leading-7 text-slate-600">{description}</p>}
      <label className="block text-sm">
        <span className="mb-1.5 block text-slate-700">{fieldLabel}</span>
        <textarea
          ref={box}
          value={text}
          maxLength={TEXT_MAX}
          rows={4}
          onChange={(event) => setText(event.target.value)}
          className={textareaClass}
        />
      </label>
      {extra}
      {error && <ErrorBanner message={error} />}
      <DialogFooter>
        <Button onClick={onCancel} disabled={sending}>
          انصراف
        </Button>
        <Button variant={danger ? "danger" : "primary"} onClick={submit} loading={sending}>
          {confirmLabel}
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
