/** Types and pure helpers for the «اعلان‌ها» tab (Phase 15, `GET /notifications/`). All fetching
 *  lives in the component via `usePagedQuery`/`apiPost` — this file holds only what can be tested
 *  without a network. */

export interface Notification {
  id: number;
  kind: string;
  kind_label: string;
  title: string;
  body: string;
  url: string;
  created_at: string;
  read_at: string | null;
  is_read: boolean;
}

/** Where a row sends you when clicked. The server never sends an absolute URL (`url` is always a
 *  relative path into this app, or blank), so there is nothing to validate — only a fallback. */
export function notificationHref(notification: Notification): string {
  return notification.url || "/dashboard";
}
