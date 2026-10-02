"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api-client";
import { formatJalaliDateTime } from "@/lib/jalali";
import { ORG_EVENT_TONE, describeOrgEvent, type OrgEvent } from "@/lib/organization";
import { Activity, X } from "lucide-react";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";

/**
 * «تاریخچهٔ ساختار» (Phase 16): who changed the chart and when — nodes created, renamed, moved,
 * archived or deleted, people added, removed or made مسئول, temporary covers. The same shape as
 * `ProjectActivityFeed`: a `key = filter:version` stale-guard, errors swallowed into an empty list
 * ("the trail is a nicety; never block the page"), a coloured dot per kind. With `node` set it shows
 * only that node's own history, and says so.
 */
export function OrgActivityFeed({
  node,
  version,
  onClearNode,
}: {
  node: { id: number; name: string } | null;
  version: number | string;
  onClearNode: () => void;
}) {
  const [loaded, setLoaded] = useState<{ key: string; events: OrgEvent[] } | null>(null);
  const key = `${node?.id ?? "all"}:${version}`;

  useEffect(() => {
    let cancelled = false;
    apiGet<{ results: OrgEvent[] }>("/org/activity/", { page_size: 30, node: node?.id })
      .then((response) => !cancelled && setLoaded({ key, events: response.results }))
      .catch(() => !cancelled && setLoaded({ key, events: [] }));
    return () => {
      cancelled = true;
    };
  }, [node?.id, key]);

  const events = loaded?.key === key ? loaded.events : [];

  return (
    <Card aria-label="تاریخچهٔ ساختار">
      <CardHeader
        title={node ? `تاریخچهٔ «${node.name}»` : "تاریخچهٔ ساختار"}
        icon={<Activity />}
        description={node ? undefined : "تغییرهای نمودار سازمانی و جایگاه افراد"}
      />
      {node && (
        <button
          type="button"
          onClick={onClearNode}
          className="mb-3 inline-flex items-center gap-1 text-xs text-slate-500 underline-offset-2 hover:text-slate-800 hover:underline"
        >
          <X className="size-3.5" />
          نمایش تاریخچهٔ همه
        </button>
      )}
      {events.length === 0 ? (
        <EmptyState compact icon={<Activity />} message="هنوز تغییری ثبت نشده است." />
      ) : (
        <ol className="relative max-h-[24rem] space-y-4 overflow-y-auto pe-1 before:absolute before:inset-y-2 before:right-[4.5px] before:w-px before:bg-slate-200">
          {events.map((event) => (
            <li key={event.id} className="relative flex gap-3 text-sm">
              <span
                aria-hidden
                className={`relative mt-2 size-2.5 shrink-0 rounded-full ring-4 ring-white ${ORG_EVENT_TONE[event.kind] ?? "bg-slate-400"}`}
              />
              <p className="min-w-0 text-slate-900">
                {describeOrgEvent(event)}
                <span className="text-slate-500">
                  {" "}
                  · {event.actor_name}
                  {event.actor_title ? ` (${event.actor_title})` : ""} · {formatJalaliDateTime(event.created_at)}
                </span>
              </p>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
