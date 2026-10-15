"use client";

import { useState } from "react";
import { History, LogOut, MonitorSmartphone } from "lucide-react";
import { apiPost } from "@/lib/api-client";
import { formatJalaliDateTime } from "@/lib/jalali";
import { describeDevice, type SessionsResponse } from "@/lib/sessions";
import { useApiQuery } from "@/lib/use-api-query";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { useToast } from "@/components/ui/Toast";
import { cx } from "@/components/ui/cx";

/**
 * «ورودهای اخیر» (Phase 20): the last sign-in attempts on my account, failures included, and a way to
 * end every session except this one — for a phone left signed in somewhere, or an attempt I did not make.
 */
export function SignInHistoryCard() {
  const toast = useToast();
  const [reload, setReload] = useState(0);
  const [confirming, setConfirming] = useState(false);
  const sessions = useApiQuery<SessionsResponse>("/auth/sessions/", reload);
  const events = sessions.data?.events ?? [];

  return (
    <Card aria-label="ورودهای اخیر">
      <CardHeader
        title="ورودهای اخیر"
        description={
          sessions.data
            ? `ورودها و تلاش‌های ناموفق ${sessions.data.history_days.toLocaleString("fa-IR")} روز گذشته نگه داشته می‌شوند.`
            : undefined
        }
        icon={<History />}
      />
      {sessions.loading ? (
        <p className="text-sm text-muted-foreground">در حال بارگذاری...</p>
      ) : sessions.error ? (
        <p className="text-sm text-rose-700 dark:text-rose-300">{sessions.error}</p>
      ) : events.length === 0 ? (
        <EmptyState compact icon={<MonitorSmartphone />} message="هنوز ورودی ثبت نشده است." />
      ) : (
        <ul className="divide-y divide-border rounded-xl border border-border">
          {events.map((event) => (
            <li key={event.id} className="flex items-center justify-between gap-3 px-3 py-2.5 text-sm">
              <span className="min-w-0">
                <span className="block truncate text-foreground">{describeDevice(event.user_agent)}</span>
                <span className="block text-xs text-muted-foreground">
                  {formatJalaliDateTime(event.created_at)}
                  {event.ip && (
                    <>
                      {" · "}
                      <span className="latn" dir="ltr">
                        {event.ip}
                      </span>
                    </>
                  )}
                </span>
              </span>
              <span
                className={cx(
                  "shrink-0 rounded-full px-2 py-0.5 text-xs ring-1 ring-inset",
                  event.succeeded
                    ? "bg-emerald-50 dark:bg-emerald-400/10 text-emerald-800 dark:text-emerald-300 ring-emerald-600/20"
                    : "bg-rose-50 dark:bg-rose-400/10 text-rose-800 dark:text-rose-300 ring-rose-600/20",
                )}
              >
                {event.succeeded ? "ورود" : "ناموفق"}
              </span>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-4 flex justify-end">
        <Button variant="secondary" icon={<LogOut />} onClick={() => setConfirming(true)}>
          خروج از سایر دستگاه‌ها
        </Button>
      </div>
      {confirming && (
        <ConfirmDialog
          title="خروج از سایر دستگاه‌ها"
          message="همهٔ دستگاه‌ها و مرورگرهای دیگری که با حساب شما وارد شده‌اند خارج می‌شوند. این مرورگر وارد می‌ماند."
          confirmLabel="خروج از سایر دستگاه‌ها"
          onConfirm={async () => {
            await apiPost("/auth/logout-others/");
            setConfirming(false);
            setReload((n) => n + 1);
            toast({ tone: "success", title: "از همهٔ دستگاه‌های دیگر خارج شدید." });
          }}
          onCancel={() => setConfirming(false)}
        />
      )}
    </Card>
  );
}
