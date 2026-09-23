"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api-client";
import { formatJalaliDateTime } from "@/lib/jalali";
import { PROJECT_EVENT_TONE, type ProjectActivityEvent } from "@/lib/projects";

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
    <section aria-label="فعالیت‌های پروژه" className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="mb-3 text-base font-semibold text-slate-900">فعالیت‌ها</h2>
      {events.length === 0 ? (
        <p className="text-sm text-slate-500">هنوز رویدادی ثبت نشده است.</p>
      ) : (
        <ol className="space-y-3">
          {events.map((event) => (
            <li key={event.id} className="flex gap-3 text-sm">
              <span
                aria-hidden
                className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${PROJECT_EVENT_TONE[event.kind] ?? "bg-slate-400"}`}
              />
              <div className="min-w-0">
                <p className="text-slate-900">
                  <span className="font-medium">{event.kind_label}</span>
                  {event.subject_title && <span className="text-slate-700"> — {event.subject_title}</span>}
                  <span className="text-slate-500">
                    {" "}
                    · {event.actor_name}
                    {event.actor_title ? ` (${event.actor_title})` : ""} · {formatJalaliDateTime(event.created_at)}
                  </span>
                </p>
                {event.from_status_label && event.to_status_label && (
                  <p className="mt-0.5 text-xs text-slate-500">
                    {event.from_status_label} ← {event.to_status_label}
                  </p>
                )}
                {event.note && <p className="mt-0.5 text-slate-600">{event.note}</p>}
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
