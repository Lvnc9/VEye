"use client";

import { useState } from "react";
import { ApiError, apiPatch } from "@/lib/api-client";
import type { Person } from "@/lib/organization";
import type { InternalAudit } from "@/lib/quality";
import { PersonPicker } from "@/components/PersonPicker";
import { ErrorBanner } from "@/components/StatusBanner";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogFooter } from "@/components/ui/Dialog";

/**
 * Replace the lead auditor. This is the one change still allowed while an audit runs (an auditor falls
 * ill mid-audit); the new person is told. Offered by `can_change_auditor`.
 */
export function ChangeAuditorDialog({
  audit,
  onSaved,
  onClose,
}: {
  audit: InternalAudit;
  onSaved: () => void;
  onClose: () => void;
}) {
  const [picked, setPicked] = useState<Person | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!picked) {
      setError("ممیز جدید را انتخاب کنید.");
      return;
    }
    setSending(true);
    setError(null);
    try {
      await apiPatch(`/quality/audits/${audit.id}/`, { lead_auditor: picked.id });
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تغییر ممیز ممکن نشد. دوباره تلاش کنید.");
      setSending(false);
    }
  }

  return (
    <Dialog
      label="تغییر ممیز اصلی"
      title="تغییر ممیز اصلی"
      description={`ممیز فعلی: ${audit.lead_auditor_name}. ممیز جدید از این تغییر باخبر می‌شود و از این پس او ممیزی را پیش می‌برد.`}
      onClose={onClose}
      busy={sending}
    >
      {picked ? (
        <p className="flex items-center gap-2 rounded-xl bg-brand-50 px-3 py-2 text-sm text-brand-900">
          <Avatar name={picked.full_name} size="sm" />
          {picked.full_name}
          <button type="button" onClick={() => setPicked(null)} className="ms-auto text-xs underline">
            تغییر
          </button>
        </p>
      ) : (
        <PersonPicker
          id="auditor-change"
          ariaLabel="جست‌وجوی ممیز جدید"
          pickLabel="انتخاب"
          doneLabel="ممیز فعلی"
          excludedIds={new Set([audit.lead_auditor])}
          onPick={setPicked}
        />
      )}
      {error && <ErrorBanner message={error} />}
      <DialogFooter>
        <Button onClick={onClose} disabled={sending}>
          انصراف
        </Button>
        <Button variant="primary" onClick={submit} loading={sending}>
          تغییر ممیز
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
