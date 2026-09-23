"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, apiGet } from "@/lib/api-client";
import {
  LIST_POLL_MS,
  lastMessageLine,
  sortConversations,
  unreadBadge,
  type Conversation,
} from "@/lib/chat";
import { formatJalaliDateTime } from "@/lib/jalali";
import { initials } from "@/lib/organization";
import type { Paginated } from "@/lib/types";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
import { ChatThread } from "./ChatThread";

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const LIST_PAGE_SIZE = 200;

/**
 * «گفتگوها»: the conversation list (polled for unread counts and order) beside the open thread.
 * The selection is the URL's `?c=` (owned by the page) — where the chart's «گفتگو» button lands. A
 * conversation that is readable but not in the list yet is fetched on its own.
 */
export function ConversationsTab({
  selectedId,
  onSelect,
}: {
  selectedId: number | null;
  onSelect: (id: number) => void;
}) {
  const [list, setList] = useState<{ rows: Conversation[]; error: string | null } | null>(null);
  const [version, setVersion] = useState(0);
  const [extra, setExtra] = useState<{ id: number; conversation: Conversation | null; error: string | null } | null>(null);

  useEffect(() => {
    let stopped = false;
    async function run() {
      while (!stopped) {
        try {
          const page = await apiGet<Paginated<Conversation>>("/chat/conversations/", { page_size: LIST_PAGE_SIZE });
          if (!stopped) setList({ rows: sortConversations(page.results), error: null });
        } catch (err) {
          if (!stopped) {
            setList((current) => ({
              rows: current?.rows ?? [],
              error: err instanceof ApiError ? err.message : "دریافت گفتگوها ممکن نشد.",
            }));
          }
        }
        await sleep(LIST_POLL_MS);
        while (!stopped && typeof document !== "undefined" && document.visibilityState !== "visible") {
          await sleep(LIST_POLL_MS);
        }
      }
    }
    run();
    return () => {
      stopped = true;
    };
  }, [version]);

  const refresh = useCallback(() => setVersion((v) => v + 1), []);

  const rows = list?.rows ?? [];
  const listed = rows.find((c) => c.id === selectedId) ?? null;

  // The selected conversation is not in the list: fetch it alone (a 404 means it is not readable).
  useEffect(() => {
    if (selectedId === null || !list || listed) return;
    let cancelled = false;
    apiGet<Conversation>(`/chat/conversations/${selectedId}/`)
      .then((conversation) => !cancelled && setExtra({ id: selectedId, conversation, error: null }))
      .catch(
        (err) =>
          !cancelled &&
          setExtra({
            id: selectedId,
            conversation: null,
            error: err instanceof ApiError ? err.message : "این گفتگو در دسترس نیست.",
          }),
      );
    return () => {
      cancelled = true;
    };
  }, [selectedId, list, listed]);

  const selected = listed ?? (extra?.id === selectedId ? extra.conversation : null);
  const selectedError = !listed && extra?.id === selectedId ? extra.error : null;

  return (
    <div className="flex h-[calc(100vh-13rem)] min-h-[28rem] overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <aside aria-label="فهرست گفتگوها" className="flex w-80 flex-shrink-0 flex-col border-l border-slate-200">
        {list?.error && (
          <div className="p-3">
            <ErrorBanner message={list.error} />
          </div>
        )}
        {!list ? (
          <div className="p-3">
            <LoadingBanner />
          </div>
        ) : rows.length === 0 ? (
          <p className="p-5 text-sm leading-7 text-slate-500">
            هنوز گفتگویی ندارید. از صفحهٔ ساختار سازمان روی یک شخص یا گره بزنید و «گفتگو» را انتخاب کنید.
          </p>
        ) : (
          <ul className="flex-1 overflow-y-auto">
            {rows.map((conversation) => (
              <li key={conversation.id}>
                <ConversationRow
                  conversation={conversation}
                  active={conversation.id === selectedId}
                  onSelect={() => onSelect(conversation.id)}
                />
              </li>
            ))}
          </ul>
        )}
      </aside>

      <div className="min-w-0 flex-1">
        {selected ? (
          <ChatThread key={selected.id} conversation={selected} onActivity={refresh} />
        ) : selectedError ? (
          <div className="p-5">
            <ErrorBanner message={selectedError} />
          </div>
        ) : (
          <div className="flex h-full items-center justify-center p-5 text-sm text-slate-400">
            {selectedId !== null ? "در حال بارگذاری..." : "یک گفتگو را از فهرست انتخاب کنید."}
          </div>
        )}
      </div>
    </div>
  );
}

function ConversationRow({
  conversation,
  active,
  onSelect,
}: {
  conversation: Conversation;
  active: boolean;
  onSelect: () => void;
}) {
  const badge = unreadBadge(conversation.unread_count);
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={active ? "true" : undefined}
      className={`flex w-full items-start gap-3 border-b border-slate-100 px-4 py-3 text-right transition-colors ${
        active ? "bg-slate-100" : "hover:bg-slate-50"
      }`}
    >
      <span
        aria-hidden
        className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold text-white ${
          conversation.kind === "DIRECT" ? "bg-slate-700" : "bg-teal-700"
        }`}
      >
        {conversation.kind === "DIRECT" ? initials(conversation.title) : "#"}
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center justify-between gap-2">
          <span className={`truncate text-sm ${badge ? "font-bold text-slate-900" : "font-medium text-slate-800"}`}>
            {conversation.title}
          </span>
          {badge && (
            <span className="flex-shrink-0 rounded-full bg-red-600 px-1.5 py-0.5 text-[10px] font-bold text-white" aria-label={`${conversation.unread_count} پیام خوانده‌نشده`}>
              {badge}
            </span>
          )}
        </span>
        <span className="mt-0.5 block truncate text-xs text-slate-500">{lastMessageLine(conversation)}</span>
        {conversation.last_message_at && (
          <span className="mt-0.5 block text-[10px] text-slate-400">{formatJalaliDateTime(conversation.last_message_at)}</span>
        )}
      </span>
    </button>
  );
}
