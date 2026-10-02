/** The «گزارش‌ها» screen's pure logic (Phase 17): which URL an export button calls. All fetching and
 *  saving lives in the component; this is what can be tested without a network. */

export interface DocumentExportFilters {
  group?: string;
  category?: string;
  status?: string;
  search?: string;
}

/** `/reports/documents/export/` with only the filters that are set — an empty value is "no filter",
 *  never `?group=` (the register's own filters treat an unknown value as matching nothing). */
export function documentsExportPath(filters: DocumentExportFilters = {}): string {
  const params = new URLSearchParams();
  for (const key of ["group", "category", "status", "search"] as const) {
    const value = filters[key]?.trim();
    if (value) params.set(key, value);
  }
  const query = params.toString();
  return `/reports/documents/export/${query ? `?${query}` : ""}`;
}

export function projectsExportPath(archived = false): string {
  return `/reports/projects/export/${archived ? "?archived=1" : ""}`;
}
