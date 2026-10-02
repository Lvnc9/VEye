"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api-client";
import { formatJalaliDateTime } from "@/lib/jalali";
import { QUALITY_EVENT_TONE, qualityEventDetail, type QualityEvent } from "@/lib/quality";
import { Activity } from "lucide-react";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";

/**
 * A history rail — the same shape as `ProjectActivityFeed`: a `key = path:version` stale-guard so a fast
 * navigation never flashes the previous record's feed, errors swallowed into an empty list ("the trail is
 * a nicety; never block the page"), a coloured dot per kind. `version` lets the page force a refetch after
 * an action without changing the URL. One component for a non-conformance's rail and an audit's: only the
 * endpoint and the heading differ (`NcActivityFeed`, `AuditActivityFeed` below).
 */
function QualityActivityFeed({
  path,
  label,
  version,
  showFindingTitle = false,
}: {
  path: string;
  label: string;
  version: number | string;
  /** On an audit's rail a finding's line names the finding; on the finding's own rail that is redundant. */
  showFindingTitle?: boolean;
}) {
  const [loaded, setLoaded] = useState<{ key: string; events: QualityEvent[] } | null>(null);
  const key = `${path}:${version}`;

  useEffect(() => {
    let cancelled = false;
    apiGet<{ results: QualityEvent[] }>(path, { page_size: 50 })
      .then((response) => !cancelled && setLoaded({ key, events: response.results }))
      .catch(() => !cancelled && setLoaded({ key, events: [] }));
    return () => {
      cancelled = true;
    };
  }, [path, key]);

  const events = loaded?.key === key ? loaded.events : [];

  return (
    <Card aria-label={label} className="lg:sticky lg:top-4">
      <CardHeader title="تاریخچه" icon={<Activity />} />
      {events.length === 0 ? (
        <EmptyState compact icon={<Activity />} message="هنوز رویدادی ثبت نشده است." />
      ) : (
        <ol className="relative max-h-[70vh] space-y-4 overflow-y-auto pe-1 before:absolute before:inset-y-2 before:right-[4.5px] before:w-px before:bg-slate-200">
          {events.map((event) => {
            const detail = qualityEventDetail(event);
            return (
              <li key={event.id} className="relative flex gap-3 text-sm">
                <span
                  aria-hidden
                  className={`relative mt-2 size-2.5 shrink-0 rounded-full ring-4 ring-white ${QUALITY_EVENT_TONE[event.kind] ?? "bg-slate-400"}`}
                />
                <div className="min-w-0">
                  <p className="text-slate-900">
                    <span className="font-bold">{event.kind_label}</span>
                    {event.subject_title && (event.kind.startsWith("action_") || (showFindingTitle && event.kind === "finding_raised")) && (
                      <span className="text-slate-700"> — {event.subject_title}</span>
                    )}
                    <span className="text-slate-500">
                      {" "}
                      · {event.actor_name}
                      {event.actor_title ? ` (${event.actor_title})` : ""} · {formatJalaliDateTime(event.created_at)}
                    </span>
                  </p>
                  {detail && <p className="mt-1 whitespace-pre-line text-xs leading-6 text-slate-600">{detail}</p>}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </Card>
  );
}

export function NcActivityFeed({ ncId, version }: { ncId: number; version: number | string }) {
  return <QualityActivityFeed path={`/quality/nonconformances/${ncId}/activity/`} label="تاریخچهٔ عدم‌انطباق" version={version} />;
}

export function AuditActivityFeed({ auditId, version }: { auditId: number; version: number | string }) {
  return <QualityActivityFeed path={`/quality/audits/${auditId}/activity/`} label="تاریخچهٔ ممیزی" version={version} showFindingTitle />;
}
