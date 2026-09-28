"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api-client";
import { formatJalali } from "@/lib/jalali";
import type { DocumentEvent } from "@/lib/types";
import { GitCommitVertical } from "lucide-react";
import { Card, CardHeader } from "@/components/ui/Card";

const TONE: Record<string, string> = {
  submitted: "bg-brand-500",
  confirmed: "bg-amber-500",
  approved: "bg-emerald-500",
  returned: "bg-rose-500",
  superseded: "bg-slate-400",
  imported: "bg-violet-400",
};

/** The audit trail of one document: who submitted, confirmed, approved or
 *  returned it (and why), oldest first. Renders nothing until there is a step. */
export function WorkflowTimeline({ documentId, version }: { documentId: number; version: string }) {
  const [loaded, setLoaded] = useState<{ key: string; events: DocumentEvent[] } | null>(null);
  const key = `${documentId}:${version}`;

  useEffect(() => {
    let cancelled = false;
    apiGet<DocumentEvent[]>(`/documents/${documentId}/history/`)
      .then((events) => !cancelled && setLoaded({ key, events }))
      .catch(() => !cancelled && setLoaded({ key, events: [] })); // the trail is a nicety; never block the page
    return () => {
      cancelled = true;
    };
  }, [documentId, key]);

  const events = loaded?.key === key ? loaded.events : [];
  if (events.length === 0) return null;

  return (
    <Card aria-label="سوابق گردش کار" className="p-5">
      <CardHeader title="سوابق گردش کار" icon={<GitCommitVertical />} className="mb-3" />
      <ol className="relative space-y-3.5 before:absolute before:inset-y-2 before:right-[4.5px] before:w-px before:bg-slate-200">
        {events.map((event) => (
          <li key={event.id} className="relative flex gap-3 text-sm">
            <span
              aria-hidden
              className={`relative mt-2 size-2.5 shrink-0 rounded-full ring-4 ring-white ${TONE[event.kind] ?? "bg-slate-400"}`}
            />
            <div className="min-w-0">
              <p className="text-slate-900">
                <span className="font-bold">{event.kind_label}</span>
                <span className="text-slate-500">
                  {" "}
                  — {event.actor_name}
                  {event.actor_title ? ` (${event.actor_title})` : ""} · {formatJalali(event.created_at)}
                </span>
              </p>
              {event.reason && <p className="mt-1 rounded-lg bg-slate-50 px-2.5 py-1 text-slate-600">{event.reason}</p>}
            </div>
          </li>
        ))}
      </ol>
    </Card>
  );
}
