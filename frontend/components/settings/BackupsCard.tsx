"use client";

import { useEffect, useState } from "react";
import { DatabaseBackup, Play } from "lucide-react";
import { ApiError, apiPost } from "@/lib/api-client";
import { backupHealth, type BackupsResponse } from "@/lib/backups";
import { formatSize } from "@/lib/file-size";
import { formatJalaliDateTime } from "@/lib/jalali";
import { useApiQuery } from "@/lib/use-api-query";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { useToast } from "@/components/ui/Toast";
import { cx } from "@/components/ui/cx";

const STATUS_TONE = {
  running: "bg-brand-50 text-brand-800 ring-brand-600/20",
  succeeded: "bg-emerald-50 text-emerald-800 ring-emerald-600/20",
  failed: "bg-rose-50 text-rose-800 ring-rose-600/20",
} as const;

/**
 * «پشتیبان‌گیری» (Phase 20, owner's decision 2026-10-15): the nightly database + media backups — when the
 * last good one was made, the recent runs, and a button to make one now. Only the مدیر عامل and the
 * developer account see it (the server says 403 to anyone else).
 */
export function BackupsCard() {
  const toast = useToast();
  const [reload, setReload] = useState(0);
  const [starting, setStarting] = useState(false);
  const backups = useApiQuery<BackupsResponse>("/ops/backups/", reload);
  const runs = backups.data?.runs ?? [];
  const health = backupHealth(runs);

  // While one runs, look again every few seconds so the row turns green (or red) by itself.
  useEffect(() => {
    if (!health.running) return;
    const timer = setTimeout(() => setReload((n) => n + 1), 5000);
    return () => clearTimeout(timer);
  }, [health.running, reload]);

  async function startNow() {
    setStarting(true);
    try {
      await apiPost("/ops/backups/run/");
      toast({ tone: "success", title: "پشتیبان‌گیری آغاز شد." });
      setReload((n) => n + 1);
    } catch (error) {
      toast({ tone: "danger", title: error instanceof ApiError ? error.message : "پشتیبان‌گیری آغاز نشد." });
    } finally {
      setStarting(false);
    }
  }

  return (
    <Card aria-label="پشتیبان‌گیری">
      <CardHeader
        title="پشتیبان‌گیری"
        description={
          backups.data
            ? `${backups.data.schedule}، از پایگاه داده و فایل‌ها. ${backups.data.keep.toLocaleString("fa-IR")} نسخهٔ آخر روی سرور می‌ماند.`
            : undefined
        }
        icon={<DatabaseBackup />}
        actions={
          <Button
            variant="secondary"
            size="sm"
            icon={<Play />}
            loading={starting}
            disabled={health.running}
            onClick={startNow}
          >
            پشتیبان‌گیری الان
          </Button>
        }
      />
      {backups.loading ? (
        <p className="text-sm text-slate-500">در حال بارگذاری...</p>
      ) : backups.error ? (
        <p className="text-sm text-rose-700">{backups.error}</p>
      ) : (
        <div className="space-y-4">
          {health.state === "none" ? (
            <Alert tone="warning" title="هنوز هیچ پشتیبانی ساخته نشده است.">
              نخستین پشتیبان امشب ساخته می‌شود؛ یا همین حالا «پشتیبان‌گیری الان» را بزنید.
            </Alert>
          ) : health.state === "stale" ? (
            <Alert tone="danger" title="پشتیبان‌گیری شبانه از کار افتاده است.">
              آخرین پشتیبان موفق: {formatJalaliDateTime(health.lastSuccess?.finished_at ?? health.lastSuccess?.started_at)}.
            </Alert>
          ) : (
            <Alert tone="success">
              آخرین پشتیبان موفق: {formatJalaliDateTime(health.lastSuccess?.finished_at ?? health.lastSuccess?.started_at)}
              {" — "}
              <bdi dir="ltr">{formatSize(health.lastSuccess?.size_bytes ?? 0)}</bdi>
            </Alert>
          )}
          {runs.length === 0 ? (
            <EmptyState compact icon={<DatabaseBackup />} message="فهرست پشتیبان‌ها خالی است." />
          ) : (
            <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200">
              {runs.map((run) => (
                <li key={run.id} className="flex items-start justify-between gap-3 px-3 py-2.5 text-sm">
                  <span className="min-w-0">
                    <span className="block text-slate-900">
                      {formatJalaliDateTime(run.started_at)}
                      <span className="text-xs text-slate-500">
                        {" · "}
                        {run.trigger_label}
                        {run.requested_by && ` (${run.requested_by})`}
                      </span>
                    </span>
                    {run.status === "succeeded" && (
                      <span className="block text-xs text-slate-500">
                        <bdi dir="ltr">{formatSize(run.size_bytes)}</bdi>
                        {run.pruned && " · فایل‌ها طبق سیاست نگهداری پاک شده‌اند"}
                      </span>
                    )}
                    {run.status === "failed" && run.error && (
                      <span className="block break-words text-xs text-rose-700">{run.error}</span>
                    )}
                  </span>
                  <span
                    className={cx("shrink-0 rounded-full px-2 py-0.5 text-xs ring-1 ring-inset", STATUS_TONE[run.status])}
                  >
                    {run.status_label}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <p className="text-xs leading-6 text-slate-500">
            فایل‌ها در پوشهٔ <span className="latn">backups</span> کنار فایل docker-compose روی سرور ذخیره می‌شوند. اگر دیسک
            سرور از دست برود پشتیبان‌ها هم می‌روند؛ هر از گاهی یک نسخه را بیرون از سرور نگه دارید (راهنمای README).
          </p>
        </div>
      )}
    </Card>
  );
}
