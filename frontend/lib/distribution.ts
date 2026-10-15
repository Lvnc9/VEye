/**
 * Read acknowledgment (Phase 21): approved documents distributed to the people who must read them.
 * Relative imports only (vitest has no `@/` alias).
 */
import { apiPost } from "./api-client";

export interface PendingRead {
  document: { id: number; full_code: string; title: string; status: string; group_label: string };
  asked_at: string;
}

/** `GET /distribution/documents/{id}/` — am I asked to read it, and may I see who has. */
export interface DocumentReading {
  mine: { acknowledged_at: string | null } | null;
  can_view_coverage: boolean;
  total: number | null;
  acknowledged: number | null;
}

export interface CoveragePerson {
  name: string;
  title: string;
  acknowledged_at: string | null;
}

export interface Coverage {
  document: { id: number; full_code: string; title: string };
  total: number;
  acknowledged: number;
  percent: number | null;
  groups: { node_name: string; people: CoveragePerson[] }[];
}

export function acknowledge(documentId: number): Promise<{ acknowledged_at: string }> {
  return apiPost(`/distribution/documents/${documentId}/acknowledge/`);
}

/** "۳ از ۸ نفر (۳۸٪)" — or a dash when nobody was asked. */
export function coverageLabel(acknowledged: number | null, total: number | null): string {
  if (!total) return "—";
  const percent = Math.round((100 * (acknowledged ?? 0)) / total);
  return `${(acknowledged ?? 0).toLocaleString("fa-IR")} از ${total.toLocaleString("fa-IR")} نفر (${percent.toLocaleString("fa-IR")}٪)`;
}

/** Who has not read it yet, per group — the people a lead may want to remind. */
export function unreadCount(coverage: Coverage): number {
  return coverage.total - coverage.acknowledged;
}
