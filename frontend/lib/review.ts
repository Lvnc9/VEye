/**
 * Periodic review (Phase 21): the badge a document in force wears when its review comes near or has passed,
 * the interval choices, and the two calls. Relative imports only (vitest has no `@/` alias).
 */
import { apiPost } from "./api-client";
import type { DocumentRow, ReviewState } from "./types";

export const REVIEW_STATE_LABELS: Record<ReviewState, string> = {
  due: "نزدیک موعد بازنگری",
  overdue: "بازنگری عقب افتاده",
};

/** The register's filter. */
export const REVIEW_FILTER_OPTIONS: { value: ReviewState | ""; label: string }[] = [
  { value: "", label: "همهٔ مستندات" },
  { value: "due", label: "نزدیک یا گذشته از موعد بازنگری" },
  { value: "overdue", label: "گذشته از موعد بازنگری" },
];

/** The intervals offered in the designer and «تنظیمات» (months; 0 = no periodic review). */
export const REVIEW_INTERVAL_CHOICES = [0, 3, 6, 12, 18, 24, 36] as const;

export function reviewIntervalLabel(months: number): string {
  if (months <= 0) return "بدون بازنگری دوره‌ای";
  if (months % 12 === 0) {
    const years = months / 12;
    return years === 1 ? "هر سال" : `هر ${years.toLocaleString("fa-IR")} سال`;
  }
  return `هر ${months.toLocaleString("fa-IR")} ماه`;
}

/** Interval choices, keeping a stored value that is not in the list (set through the API or an old default). */
export function intervalChoices(current: number): number[] {
  const set = new Set<number>([...REVIEW_INTERVAL_CHOICES, current]);
  return [...set].sort((a, b) => a - b);
}

export const REVIEW_NOTE_MAX_LENGTH = 1000;

export function markReviewed(documentId: number, note: string): Promise<DocumentRow> {
  return apiPost<DocumentRow>(`/documents/${documentId}/mark-reviewed/`, { note: note.trim() });
}

export function setReviewInterval(documentId: number, months: number): Promise<DocumentRow> {
  return apiPost<DocumentRow>(`/documents/${documentId}/review-interval/`, { months });
}
