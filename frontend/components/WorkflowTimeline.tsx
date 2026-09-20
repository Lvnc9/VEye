"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api-client";
import { formatJalali } from "@/lib/jalali";
import type { DocumentEvent } from "@/lib/types";

const TONE: Record<string, string> = {
  submitted: "bg-blue-500",
  confirmed: "bg-amber-500",
  approved: "bg-green-600",
  returned: "bg-red-500",
  superseded: "bg-slate-400",
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
    <section aria-label="سوابق گردش کار" className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="mb-3 text-base font-semibold text-slate-900">سوابق گردش کار</h2>
      <ol className="space-y-3">
        {events.map((event) => (
          <li key={event.id} className="flex gap-3 text-sm">
            <span aria-hidden className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${TONE[event.kind] ?? "bg-slate-400"}`} />
            <div>
              <p className="text-slate-900">
                <span className="font-medium">{event.kind_label}</span>
                <span className="text-slate-500">
                  {" "}
                  — {event.actor_name}
                  {event.actor_title ? ` (${event.actor_title})` : ""} · {formatJalali(event.created_at)}
                </span>
              </p>
              {event.reason && <p className="mt-0.5 text-slate-600">{event.reason}</p>}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
