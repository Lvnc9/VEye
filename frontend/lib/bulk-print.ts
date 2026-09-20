/**
 * چاپ لیست (Phase 6): a ZIP of already-built official PDFs, for the selected rows
 * or — with nothing selected — the register's current filter. Building the URLs is
 * kept pure here; the server decides what is ready (and never renders).
 * Relative imports only: vitest has no `@/` alias.
 */
import { API_BASE_URL } from "./api-client";
import type { DocumentFilters } from "./types";

/** More ids than this and the URL gets unwieldy; the server refuses beyond it too. */
export const MAX_SELECTED_IDS = 200;

export type BulkSelection = { ids: number[] } | { filters: DocumentFilters };

/** Query string for either endpoint. Explicit ids win; otherwise the filters
 *  (empty ones dropped), and no filters at all means "every document". */
export function bulkQuery(selection: BulkSelection): string {
  const params = new URLSearchParams();
  if ("ids" in selection && selection.ids.length > 0) {
    params.set("ids", selection.ids.slice(0, MAX_SELECTED_IDS).join(","));
  } else if ("filters" in selection) {
    for (const [key, value] of Object.entries(selection.filters)) {
      if (typeof value === "string" && value.trim() !== "") params.set(key, value.trim());
    }
  }
  return params.toString();
}

export function preflightPath(selection: BulkSelection): string {
  const query = bulkQuery(selection);
  return `/documents/bulk-print/preflight/${query ? `?${query}` : ""}`;
}

/** Absolute URL of the ZIP: the browser navigates to it with its own cookie. */
export function downloadUrl(selection: BulkSelection): string {
  const query = bulkQuery(selection);
  return `${API_BASE_URL}/documents/bulk-print/${query ? `?${query}` : ""}`;
}

/** The button's hint: what a click would print. */
export function selectionLabel(selectedCount: number, filtersActive: boolean): string {
  if (selectedCount > 0) return `${selectedCount} مستند انتخاب‌شده`;
  return filtersActive ? "همهٔ نتایج فیلتر" : "همهٔ مستندات";
}
