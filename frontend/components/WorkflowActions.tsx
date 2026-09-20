"use client";

import { useState } from "react";
import { returnDocument, signStep, STEP_DONE, STEP_LABELS, STEP_PROMPTS, workflowControls } from "@/lib/workflow";
import type { DocumentRow } from "@/lib/types";
import { SignatureDialog } from "@/components/SignatureDialog";
import { ReturnDialog } from "@/components/ReturnDialog";

interface Props {
  row: DocumentRow;
  /** Called after a step succeeded, with the message to show and the fresh row. */
  onDone: (message: string, updated: DocumentRow) => void;
  /** Blocks signing with this reason (the designer holds it while edits are unsaved,
   *  because the server would sign what was last *saved*). */
  hold?: string;
}

const primary = "rounded bg-slate-900 px-3 py-1 text-xs font-medium text-white hover:bg-slate-700";
const secondary = "rounded border border-red-300 bg-white px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-50";
const disabled = "cursor-not-allowed rounded bg-slate-200 px-3 py-1 text-xs font-medium text-slate-500";

/**
 * A register row's sign-off buttons (Phase 5). Which ones appear is decided by
 * the server (`row.workflow`); the dialogs collect the signature or the reason
 * and call the API.
 */
export function WorkflowActions({ row, onDone, hold }: Props) {
  const [dialog, setDialog] = useState<"sign" | "return" | null>(null);
  const controls = workflowControls(row.workflow);
  const step = controls.primary?.step;

  if (!controls.primary) return null;

  return (
    <>
      <button
        type="button"
        disabled={controls.primary.disabled || Boolean(hold)}
        title={controls.primary.title ?? hold}
        onClick={() => setDialog("sign")}
        className={controls.primary.disabled || hold ? disabled : primary}
      >
        {controls.primary.label}
      </button>
      {controls.canReturn && (
        <button type="button" onClick={() => setDialog("return")} className={secondary}>
          مرجوع
        </button>
      )}

      {dialog === "sign" && step && (
        <SignatureDialog
          title={`${STEP_LABELS[step]} — مستند ${row.full_code}`}
          prompt={STEP_PROMPTS[step]}
          confirmLabel={STEP_LABELS[step]}
          onCancel={() => setDialog(null)}
          onSubmit={async (image) => {
            const updated = await signStep(row.id, step, image);
            setDialog(null);
            onDone(STEP_DONE[step](row.full_code), updated);
          }}
        />
      )}
      {dialog === "return" && (
        <ReturnDialog
          code={row.full_code}
          onCancel={() => setDialog(null)}
          onSubmit={async (reason) => {
            const updated = await returnDocument(row.id, reason);
            setDialog(null);
            onDone(`مستند ${row.full_code} مرجوع شد و به پیش‌نویس بازگشت.`, updated);
          }}
        />
      )}
    </>
  );
}
