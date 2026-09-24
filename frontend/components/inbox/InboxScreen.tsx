"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { parseConversationParam, parseInboxTab, unreadBadge, type InboxTab } from "@/lib/chat";
import { useInboxSummary } from "@/lib/use-inbox-summary";
import { AwaitingTab } from "./AwaitingTab";
import { ConversationsTab } from "./ConversationsTab";

const TAB_SUMMARY_POLL_MS = 15000;

/** کارتابل (docs/11 §3.6): two tabs. Both the tab and the open conversation live in the URL
 *  (`?tab=awaiting`, `?c=<id>`), so a link from the chart, a reload or the back button all land in
 *  the same place. */
export function InboxScreen() {
  const router = useRouter();
  const search = useSearchParams();
  const selectedId = parseConversationParam(search.get("c"));
  const tab: InboxTab = selectedId !== null ? "conversations" : parseInboxTab(search.get("tab"));
  const summary = useInboxSummary(TAB_SUMMARY_POLL_MS);

  const tabs: { id: InboxTab; label: string; count: number }[] = [
    { id: "conversations", label: "گفتگوها", count: summary?.unread_messages ?? 0 },
    { id: "awaiting", label: "منتظر اقدام", count: (summary?.awaiting_documents ?? 0) + (summary?.due_objectives ?? 0) },
  ];

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">کارتابل</h1>
        <p className="mt-1 text-sm text-slate-500">گفتگوهای شما و کارهایی که منتظر اقدام شماست</p>
      </header>

      <div role="tablist" aria-label="بخش‌های کارتابل" className="flex gap-1 border-b border-slate-200">
        {tabs.map((item) => {
          const badge = unreadBadge(item.count);
          return (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={tab === item.id}
              onClick={() => router.replace(item.id === "awaiting" ? "/inbox?tab=awaiting" : "/inbox", { scroll: false })}
              className={`-mb-px flex items-center gap-2 border-b-2 px-4 py-2 text-sm font-medium ${
                tab === item.id ? "border-slate-900 text-slate-900" : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              {item.label}
              {badge && <span className="rounded-full bg-red-600 px-1.5 py-0.5 text-[10px] font-bold text-white">{badge}</span>}
            </button>
          );
        })}
      </div>

      {tab === "conversations" ? (
        <ConversationsTab
          selectedId={selectedId}
          onSelect={(id) => router.replace(`/inbox?c=${id}`, { scroll: false })}
          onBack={() => router.replace("/inbox", { scroll: false })}
        />
      ) : (
        <AwaitingTab summary={summary} />
      )}
    </div>
  );
}
