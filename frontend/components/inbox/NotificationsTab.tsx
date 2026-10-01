"use client";

import Link from "next/link";
import { useState } from "react";
import { Bell, CheckCheck } from "lucide-react";
import { apiPost } from "@/lib/api-client";
import { usePagedQuery } from "@/lib/use-paged-query";
import { notificationHref, type Notification } from "@/lib/notifications";
import { formatJalaliDateTime } from "@/lib/jalali";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { SkeletonLines } from "@/components/ui/Skeleton";

/** «اعلان‌ها» (Phase 15): the persisted feed behind the badge — unlike the other two کارتابل tabs,
 *  every row here can be marked read, one at a time or all together. */
export function NotificationsTab({ onChanged }: { onChanged?: () => void }) {
  const [reload, setReload] = useState(0);
  const [busy, setBusy] = useState(false);
  const { rows, loading, error } = usePagedQuery<Notification>("/notifications/", {}, reload);
  const unread = rows.filter((row) => !row.is_read);

  async function markRead(notification: Notification) {
    if (notification.is_read) return;
    try {
      await apiPost(`/notifications/${notification.id}/read/`, {});
      setReload((n) => n + 1);
      onChanged?.();
    } catch {
      // a failed mark-read is harmless: the row just stays unread until the next try
    }
  }

  async function markAllRead() {
    setBusy(true);
    try {
      await apiPost("/notifications/read-all/", {});
      setReload((n) => n + 1);
      onChanged?.();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card aria-label="اعلان‌ها">
      <div className="flex items-center justify-between gap-3 pb-3">
        <h2 className="flex items-center gap-2 font-bold text-slate-900">
          <Bell className="size-4" /> اعلان‌ها
        </h2>
        {unread.length > 0 && (
          <Button variant="ghost" size="sm" onClick={markAllRead} disabled={busy}>
            <CheckCheck className="size-4" /> علامت‌زدن همه به‌عنوان خوانده‌شده
          </Button>
        )}
      </div>

      {loading && rows.length === 0 ? (
        <SkeletonLines rows={4} />
      ) : error ? (
        <EmptyState compact icon={<Bell />} message={error} />
      ) : rows.length === 0 ? (
        <EmptyState compact icon={<Bell />} message="اعلانی ندارید." />
      ) : (
        <ul className="-mx-2 divide-y divide-slate-100">
          {rows.map((notification) => (
            <li
              key={notification.id}
              className={`rounded-xl px-2 py-3 text-sm transition-colors hover:bg-slate-50 ${
                notification.is_read ? "" : "bg-brand-50/50"
              }`}
            >
              <Link
                href={notificationHref(notification)}
                onClick={() => markRead(notification)}
                className="flex flex-col gap-1"
              >
                <span className={`flex items-center gap-2 ${notification.is_read ? "text-slate-700" : "font-bold text-slate-900"}`}>
                  {!notification.is_read && <span className="size-2 shrink-0 rounded-full bg-brand-600" aria-hidden />}
                  {notification.title}
                </span>
                {notification.body && <span className="text-slate-500">{notification.body}</span>}
                <span className="text-xs text-slate-400">{formatJalaliDateTime(notification.created_at)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
