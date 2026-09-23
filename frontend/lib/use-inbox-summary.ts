"use client";

import { useEffect, useState } from "react";
import { apiGet } from "./api-client";
import { BADGE_POLL_MS, type InboxSummary } from "./chat";

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** GET /dashboard/inbox/, refreshed every `intervalMs` while the tab is visible. A failed poll keeps
 *  the last answer (a badge is a nudge — never an error banner). */
export function useInboxSummary(intervalMs: number = BADGE_POLL_MS): InboxSummary | null {
  const [summary, setSummary] = useState<InboxSummary | null>(null);
  useEffect(() => {
    let stopped = false;
    async function run() {
      while (!stopped) {
        if (typeof document === "undefined" || document.visibilityState === "visible") {
          try {
            const next = await apiGet<InboxSummary>("/dashboard/inbox/");
            if (!stopped) setSummary(next);
          } catch {
            // keep the last value
          }
        }
        await sleep(intervalMs);
      }
    }
    run();
    return () => {
      stopped = true;
    };
  }, [intervalMs]);
  return summary;
}
