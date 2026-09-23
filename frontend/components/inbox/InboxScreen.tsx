"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { parseConversationParam } from "@/lib/chat";
import { ConversationsTab } from "./ConversationsTab";

/** کارتابل (docs/11 §3.6). The open conversation lives in the URL (`?c=<id>`), so a link from the
 *  chart, a reload or the back button all land on the same thread. */
export function InboxScreen() {
  const router = useRouter();
  const search = useSearchParams();
  const selectedId = parseConversationParam(search.get("c"));

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">کارتابل</h1>
        <p className="mt-1 text-sm text-slate-500">گفتگوهای خصوصی و گروهی شما</p>
      </header>
      <ConversationsTab selectedId={selectedId} onSelect={(id) => router.replace(`/inbox?c=${id}`, { scroll: false })} />
    </div>
  );
}
