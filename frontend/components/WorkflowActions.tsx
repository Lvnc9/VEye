"use client";

import { useState } from "react";
import { returnDocument, signStep, STEP_DONE, STEP_LABELS, STEP_PROMPTS, workflowControls } from "@/lib/workflow";
import type { DocumentRow } from "@/lib/types";
import { SignatureDialog } from "@/components/SignatureDialog";
import { ReturnDialog } from "@/components/ReturnDialog";
import { Undo2, PenLine } from "lucide-react";
import { Button } from "@/components/ui/Button";

interface Props {
  row: DocumentRow;
  /** Called after a step succeeded, with the message to show and the fresh row. */
  onDone: (message: string, updated: DocumentRow) => void;
  /** Blocks signing with this reason (the designer holds it while edits are unsaved,
   *  because the server would sign what was last *saved*). */
  hold?: string;
}


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
      <Button
        size="xs"
        variant="primary"
        icon={<PenLine />}
        disabled={controls.primary.disabled || Boolean(hold)}
        title={hold}
        onClick={() => setDialog("sign")}
      >
        {controls.primary.label}
      </Button>
      {controls.canReturn && (
        <Button
          size="xs"
          variant="danger-ghost"
          icon={<Undo2 />}
          onClick={() => setDialog("return")}
          className="ring-1 ring-inset ring-rose-200"
        >
          مرجوع
        </Button>
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
