"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api-client";
import { ErrorBanner } from "@/components/StatusBanner";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogFooter } from "@/components/ui/Dialog";

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
    <Dialog label={title} title={title} onClose={onCancel} busy={busy} size="sm">
      <p className="text-sm leading-7 text-slate-600">{message}</p>
      {error && <ErrorBanner message={error} />}
      <DialogFooter>
        <Button ref={cancelRef} onClick={onCancel} disabled={busy}>
          انصراف
        </Button>
        <Button variant={danger ? "danger" : "primary"} onClick={confirm} loading={busy}>
          {busy ? "لحظه‌ای صبر کنید..." : confirmLabel}
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
