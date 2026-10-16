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
        <h2 className="flex items-center gap-2 font-bold text-foreground">
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
        <ul className="-mx-2 divide-y divide-border">
          {rows.map((notification) => (
            <li
              key={notification.id}
              className={`relative rounded-xl px-2 py-3 text-sm transition-colors hover:bg-accent/60 ${
                // Unread: a lit bar on the start edge and a soft wash of the brand colour fading across the row
                // (not a filled light background — that turns into a grey slab in the dark theme).
                notification.is_read ? "" : "bg-gradient-to-l from-primary/[0.09] via-primary/[0.02] to-transparent"
              }`}
            >
              {!notification.is_read && (
                <span
                  aria-hidden
                  className="absolute inset-y-2.5 start-0 w-[3px] rounded-full bg-primary shadow-[0_0_10px_var(--primary)]"
                />
              )}
              <Link
                href={notificationHref(notification)}
                onClick={() => markRead(notification)}
                className="flex flex-col gap-1"
              >
                <span className={`flex items-center gap-2 ${notification.is_read ? "text-soft-foreground" : "font-bold text-foreground"}`}>
                  {!notification.is_read && (
                    <span className="relative flex size-2.5 shrink-0" aria-hidden>
                      <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary opacity-60" />
                      <span className="relative inline-flex size-2.5 rounded-full bg-primary" />
                    </span>
                  )}
                  {notification.title}
                </span>
                {notification.body && <span className="text-muted-foreground">{notification.body}</span>}
                <span className="text-xs text-subtle-foreground">{formatJalaliDateTime(notification.created_at)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
