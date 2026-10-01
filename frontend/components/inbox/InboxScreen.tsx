"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { parseConversationParam, parseInboxTab, unreadBadge, type InboxTab } from "@/lib/chat";
import { useInboxSummary } from "@/lib/use-inbox-summary";
import { AwaitingTab } from "./AwaitingTab";
import { ConversationsTab } from "./ConversationsTab";
import { NotificationsTab } from "./NotificationsTab";
import { CountBadge } from "@/components/ui/Badge";
import { PageHeader } from "@/components/ui/PageHeader";
import { Tabs } from "@/components/ui/Tabs";

const TAB_SUMMARY_POLL_MS = 15000;

/** کارتابل (docs/11 §3.6, + Phase 15's اعلان‌ها tab): three tabs. The tab and the open conversation
 *  both live in the URL (`?tab=awaiting`, `?c=<id>`), so a link from the chart, a reload or the
 *  back button all land in the same place. */
export function InboxScreen() {
  const router = useRouter();
  const search = useSearchParams();
  const selectedId = parseConversationParam(search.get("c"));
  const tab: InboxTab = selectedId !== null ? "conversations" : parseInboxTab(search.get("tab"));
  const summary = useInboxSummary(TAB_SUMMARY_POLL_MS);

  const tabs: { id: InboxTab; label: string; count: number }[] = [
    { id: "conversations", label: "گفتگوها", count: summary?.unread_messages ?? 0 },
    { id: "awaiting", label: "منتظر اقدام", count: (summary?.awaiting_documents ?? 0) + (summary?.due_objectives ?? 0) },
    { id: "notifications", label: "اعلان‌ها", count: summary?.unread_notifications ?? 0 },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="کارتابل" subtitle="گفتگوهای شما و کارهایی که منتظر اقدام شماست" />

      <Tabs
        label="بخش‌های کارتابل"
        items={tabs.map((item) => {
          const badge = unreadBadge(item.count);
          return { id: item.id, label: item.label, extra: badge ? <CountBadge>{badge}</CountBadge> : null };
        })}
        value={tab}
        onChange={(id) => router.replace(id === "conversations" ? "/inbox" : `/inbox?tab=${id}`, { scroll: false })}
      />

      {tab === "conversations" ? (
        <ConversationsTab
          selectedId={selectedId}
          onSelect={(id) => router.replace(`/inbox?c=${id}`, { scroll: false })}
          onBack={() => router.replace("/inbox", { scroll: false })}
        />
      ) : tab === "awaiting" ? (
        <AwaitingTab summary={summary} />
      ) : (
        <NotificationsTab />
      )}
    </div>
  );
}
