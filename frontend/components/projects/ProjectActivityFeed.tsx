"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api-client";
import { formatJalali, formatJalaliDateTime } from "@/lib/jalali";
import { MEETING_EVENT_KINDS, PROJECT_EVENT_TONE, type ProjectActivityEvent } from "@/lib/projects";
import { ArrowLeft } from "lucide-react";
import { Activity } from "lucide-react";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";

/**
 * A project's activity feed (docs/11 §3.5) — the same shape of thing `WorkflowTimeline.tsx` is for
 * a document: the `key = id:version` stale-guard so a fast navigation between projects never shows
 * a flash of the previous one's feed, errors swallowed into an empty list ("the trail is a nicety;
 * never block the page"), a coloured dot per kind. `version` lets the caller force a refetch (e.g.
 * after adding an objective) without changing the URL.
 */
export function ProjectActivityFeed({ projectId, version }: { projectId: number; version: number | string }) {
  const [loaded, setLoaded] = useState<{ key: string; events: ProjectActivityEvent[] } | null>(null);
  const key = `${projectId}:${version}`;

  useEffect(() => {
    let cancelled = false;
    apiGet<{ results: ProjectActivityEvent[] }>(`/projects/${projectId}/activity/`, { page_size: 50 })
      .then((response) => !cancelled && setLoaded({ key, events: response.results }))
      .catch(() => !cancelled && setLoaded({ key, events: [] }));
    return () => {
      cancelled = true;
    };
  }, [projectId, key]);

  const events = loaded?.key === key ? loaded.events : [];

  return (
    <Card aria-label="فعالیت‌های پروژه" className="lg:sticky lg:top-4">
      <CardHeader title="فعالیت‌ها" icon={<Activity />} />
      {events.length === 0 ? (
        <EmptyState compact icon={<Activity />} message="هنوز رویدادی ثبت نشده است." />
      ) : (
        <ol className="relative max-h-[70vh] space-y-4 overflow-y-auto pe-1 before:absolute before:inset-y-2 before:right-[4.5px] before:w-px before:bg-slate-200">
          {events.map((event) => (
            <li key={event.id} className="relative flex gap-3 text-sm">
              <span
                aria-hidden
                className={`relative mt-2 size-2.5 shrink-0 rounded-full ring-4 ring-white ${PROJECT_EVENT_TONE[event.kind] ?? "bg-slate-400"}`}
              />
              <div className="min-w-0">
                <p className="text-slate-900">
                  <span className="font-bold">{event.kind_label}</span>
                  {event.subject_title && <span className="text-slate-700"> — {event.subject_title}</span>}
                  <span className="text-slate-500">
                    {" "}
                    · {event.actor_name}
                    {event.actor_title ? ` (${event.actor_title})` : ""} · {formatJalaliDateTime(event.created_at)}
                  </span>
                </p>
                {event.kind === "objective_due_changed" ? (
                  // objective_due_changed reuses from_status/to_status to carry raw ISO dates, not a
                  // status enum, so it has no from_status_label/to_status_label to fall back on — the
                  // labels are always blank for this kind (backend history.py's _STATUS_ENUM_BY_KIND).
                  <p className="mt-0.5 text-xs text-slate-500">
                    {formatJalali(event.from_status)} <ArrowLeft className="inline size-3" aria-label="به" /> {formatJalali(event.to_status)}
                  </p>
                ) : MEETING_EVENT_KINDS.has(event.kind) && event.to_status ? (
                  // The meeting's day, as an ISO date in to_status (backend services._meeting_event).
                  <p className="mt-0.5 text-xs text-slate-500">تاریخ جلسه: {formatJalali(event.to_status)}</p>
                ) : (
                  event.from_status_label &&
                  event.to_status_label && (
                    <p className="mt-0.5 text-xs text-slate-500">
                      {event.from_status_label} <ArrowLeft className="inline size-3" aria-label="به" /> {event.to_status_label}
                    </p>
                  )
                )}
                {event.note && <p className="mt-1 rounded-lg bg-slate-50 px-2.5 py-1 text-slate-600">{event.note}</p>}
              </div>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
