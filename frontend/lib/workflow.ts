/**
 * The sign-off workflow (Phase 5): تدوین → تایید → تصویب, and مرجوع.
 *
 * Who may do what is decided by the server (capabilities, the same-person rule,
 * the document's status) and arrives on each register row as `row.workflow`;
 * this module only turns that into buttons and makes the calls. Relative imports
 * only: vitest has no `@/` alias.
 */
import { apiPost, apiUpload } from "./api-client";
import type { DocumentRow, WorkflowState, WorkflowStep } from "./types";

export const REASON_MAX_LENGTH = 1000;

export const STEP_LABELS: Record<WorkflowStep, string> = {
  submit: "ارسال برای تایید",
  confirm: "تایید",
  approve: "تصویب",
};

/** The sentence a signer reads above the signature pad. */
export const STEP_PROMPTS: Record<WorkflowStep, string> = {
  submit: "با امضای خود، مستند را به‌عنوان تدوین‌کننده برای تایید ارسال می‌کنید. پس از ارسال، محتوا قفل می‌شود.",
  confirm: "با امضای خود، مستند را به‌عنوان تایید‌کننده تایید و برای تصویب ارسال می‌کنید.",
  approve: "با امضای خود، مستند را به‌عنوان تصویب‌کننده تصویب می‌کنید. مستند «تحت کنترل» می‌شود و بازنگری قبلی آن منسوخ خواهد شد.",
};

export const STEP_DONE: Record<WorkflowStep, (code: string) => string> = {
  submit: (code) => `مستند ${code} برای تایید ارسال شد.`,
  confirm: (code) => `مستند ${code} تایید شد و برای تصویب ارسال شد.`,
  approve: (code) => `مستند ${code} تصویب شد و تحت کنترل قرار گرفت. ساخت PDF آغاز شد.`,
};

export interface WorkflowControls {
  primary: { step: WorkflowStep; label: string; disabled: boolean } | null;
  canReturn: boolean;
  /** «بازپس‌گیری» (Phase 20) — independent of the step: the submitter usually has no step to take. */
  canWithdraw: boolean;
}

/** Buttons for one row: nothing when there is no step or the org chart gives this person no part in it
 *  (the server decides per document — authority.py; «one person per step» was retired on 2026-09-30). */
export function workflowControls(flow: WorkflowState): WorkflowControls {
  const canWithdraw = Boolean(flow.can_withdraw);
  if (flow.step === null || !flow.can_act) {
    return { primary: null, canReturn: false, canWithdraw };
  }
  return {
    primary: { step: flow.step, label: STEP_LABELS[flow.step], disabled: false },
    canReturn: flow.can_return,
    canWithdraw,
  };
}

/** Client-side mirror of the server's rule, so the dialog can say so before a round trip. */
export function validateReason(text: string): string | null {
  const reason = text.trim();
  if (!reason) return "دلیل مرجوع کردن را بنویسید.";
  if (reason.length > REASON_MAX_LENGTH) return `دلیل نباید بیش از ${REASON_MAX_LENGTH} نویسه باشد.`;
  return null;
}

export function signatureFormData(image: Blob): FormData {
  const form = new FormData();
  form.append("signature", image, "signature.png");
  return form;
}

/** Sign a step. Name, post and date are never sent: the server takes them from the session. */
export function signStep(documentId: number, step: WorkflowStep, image: Blob): Promise<DocumentRow> {
  return apiUpload<DocumentRow>(`/documents/${documentId}/${step}/`, signatureFormData(image));
}

/** «بازپس‌گیری»'s note is optional (it is the submitter's own document); only its length is checked. */
export function validateWithdrawNote(text: string): string | null {
  return text.trim().length > REASON_MAX_LENGTH ? `توضیح نباید بیش از ${REASON_MAX_LENGTH} نویسه باشد.` : null;
}

export function withdrawDocument(documentId: number, reason: string): Promise<DocumentRow> {
  return apiPost<DocumentRow>(`/documents/${documentId}/withdraw/`, { reason: reason.trim() });
}

export function returnDocument(documentId: number, reason: string): Promise<DocumentRow> {
  return apiPost<DocumentRow>(`/documents/${documentId}/return/`, { reason: reason.trim() });
}
