"use client";

import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { ApiError, apiDelete, apiGet, apiPost } from "@/lib/api-client";
import {
  MESSAGE_MAX_LENGTH,
  THREAD_POLL_MS,
  canSend,
  conversationSubtitle,
  mergeMessages,
  messageText,
  newestId,
  oldestId,
  readOnlyReason,
  shouldMarkRead,
  type ChatMessage,
  type Conversation,
  type MessagePage,
} from "@/lib/chat";
import { formatJalaliDateTime } from "@/lib/jalali";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * One open conversation. Mounted with `key={conversation.id}`, so all of its state starts fresh
 * per conversation. State is only ever written from async callbacks (this project's lint forbids a
 * synchronous setState in an effect): the first page, the `?after=` poll loop and the handlers.
 */
export function ChatThread({
  conversation,
  onActivity,
}: {
  conversation: Conversation;
  /** Something changed that the list should reflect (sent, read, deleted). */
  onActivity: () => void;
}) {
  const base = `/chat/conversations/${conversation.id}/messages/`;
  const [loaded, setLoaded] = useState<{ messages: ChatMessage[]; hasOlder: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const messages = loaded?.messages ?? [];

  const newestRef = useRef<number | null>(null);
  const markRef = useRef<number | null>(conversation.my_last_read_message_id);
  const bottomRef = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);

  // First page, then poll for newer messages until the thread closes.
  useEffect(() => {
    let stopped = false;
    async function run() {
      try {
        const page = await apiGet<MessagePage>(base);
        if (stopped) return;
        setLoaded({ messages: page.results, hasOlder: page.has_more });
        newestRef.current = newestId(page.results);
      } catch (err) {
        if (!stopped) setError(err instanceof ApiError ? err.message : "دریافت پیام‌ها ممکن نشد.");
        return;
      }
      while (!stopped) {
        await sleep(THREAD_POLL_MS);
        if (stopped) return;
        if (typeof document !== "undefined" && document.visibilityState !== "visible") continue;
        try {
          const page = await apiGet<MessagePage>(base, { after: newestRef.current ?? 0 });
          if (stopped || page.results.length === 0) continue;
          newestRef.current = newestId(page.results);
          setLoaded((current) =>
            current ? { ...current, messages: mergeMessages(current.messages, page.results) } : current,
          );
        } catch {
          // A missed poll is not worth a banner; the next one tries again.
        }
      }
    }
    run();
    return () => {
      stopped = true;
    };
  }, [base]);

  // Keep the view at the newest message unless the reader has scrolled up to read history.
  const newest = newestId(messages);
  useEffect(() => {
    if (stickToBottom.current) bottomRef.current?.scrollIntoView({ block: "end" });
  }, [newest]);

  // Move my read mark forward whenever something newer is on screen (and the tab is visible).
  useEffect(() => {
    if (!shouldMarkRead(newest, markRef.current)) return;
    if (typeof document !== "undefined" && document.visibilityState !== "visible") return;
    markRef.current = newest;
    apiPost<{ last_read_message_id: number | null }>(`/chat/conversations/${conversation.id}/read/`, { message: newest })
      .then(() => onActivity())
      .catch(() => {
        markRef.current = null; // try again on the next change
      });
  }, [newest, conversation.id, onActivity]);

  async function loadOlder() {
    const before = oldestId(messages);
    if (before === null) return;
    setLoadingOlder(true);
    stickToBottom.current = false;
    try {
      const page = await apiGet<MessagePage>(base, { before });
      setLoaded((current) =>
        current ? { messages: mergeMessages(current.messages, page.results), hasOlder: page.has_more } : current,
      );
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "دریافت پیام‌های قبلی ممکن نشد.");
    } finally {
      setLoadingOlder(false);
    }
  }

  async function send(event?: FormEvent) {
    event?.preventDefault();
    if (!canSend(draft) || sending) return;
    setSending(true);
    setActionError(null);
    try {
      const message = await apiPost<ChatMessage>(base, { body: draft.trim() });
      stickToBottom.current = true;
      setDraft("");
      markRef.current = message.id;
      newestRef.current = Math.max(newestRef.current ?? 0, message.id);
      setLoaded((current) => (current ? { ...current, messages: mergeMessages(current.messages, [message]) } : current));
      onActivity();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "ارسال پیام ممکن نشد.");
    } finally {
      setSending(false);
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      send();
    }
  }

  async function remove(message: ChatMessage) {
    if (!window.confirm("این پیام حذف شود؟ به‌جای متن آن «پیام حذف شد» نمایش داده می‌شود.")) return;
    setActionError(null);
    try {
      const updated = await apiDelete<ChatMessage>(`${base}${message.id}/`);
      setLoaded((current) => (current ? { ...current, messages: mergeMessages(current.messages, [updated]) } : current));
      onActivity();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "حذف پیام ممکن نشد.");
    }
  }

  const closed = readOnlyReason(conversation);

  return (
    <section aria-label={`گفتگو با ${conversation.title}`} className="flex h-full min-h-0 flex-col">
      <header className="border-b border-slate-200 px-5 py-3">
        <h2 className="font-semibold text-slate-900">{conversation.title}</h2>
        <p className="text-xs text-slate-500">{conversationSubtitle(conversation)}</p>
      </header>

      <div
        className="min-h-0 flex-1 space-y-2 overflow-y-auto px-5 py-4"
        onScroll={(e) => {
          const el = e.currentTarget;
          stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
        }}
      >
        {error ? (
          <ErrorBanner message={error} />
        ) : !loaded ? (
          <LoadingBanner />
        ) : (
          <>
            {loaded.hasOlder && (
              <div className="text-center">
                <button
                  type="button"
                  onClick={loadOlder}
                  disabled={loadingOlder}
                  className="text-xs text-slate-500 underline hover:text-slate-800 disabled:opacity-50"
                >
                  {loadingOlder ? "در حال بارگذاری..." : "پیام‌های قبلی"}
                </button>
              </div>
            )}
            {messages.length === 0 && (
              <p className="text-center text-sm text-slate-500">
                {conversation.can_post ? "هنوز پیامی نیست. اولین پیام را بنویسید." : "هنوز پیامی نیست."}
              </p>
            )}
            {messages.map((message) => (
              <MessageRow key={message.id} message={message} showSender={conversation.kind === "NODE"} onDelete={remove} />
            ))}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      {actionError && (
        <div className="px-5">
          <ErrorBanner message={actionError} />
        </div>
      )}
      {closed ? (
        <p className="border-t border-slate-200 bg-slate-50 px-5 py-3 text-sm text-slate-500">{closed}</p>
      ) : (
        <form onSubmit={send} className="flex items-end gap-2 border-t border-slate-200 px-5 py-3">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            rows={2}
            maxLength={MESSAGE_MAX_LENGTH}
            placeholder="پیام خود را بنویسید… (Enter برای ارسال، Shift+Enter برای خط جدید)"
            aria-label="متن پیام"
            className="min-h-[2.75rem] flex-1 resize-none rounded border border-slate-300 bg-white px-3 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={sending || !canSend(draft)}
            className="rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50"
          >
            ارسال
          </button>
        </form>
      )}
    </section>
  );
}

function MessageRow({
  message,
  showSender,
  onDelete,
}: {
  message: ChatMessage;
  showSender: boolean;
  onDelete: (message: ChatMessage) => void;
}) {
  if (message.kind === "SYSTEM") {
    return (
      <p className="py-1 text-center text-xs text-slate-400">
        {message.body} · {formatJalaliDateTime(message.created_at)}
      </p>
    );
  }
  // RTL: my messages sit at the start (right), everyone else's at the end (left).
  return (
    <div className={`flex ${message.is_mine ? "justify-start" : "justify-end"}`}>
      <div
        className={`group max-w-[75%] rounded-lg px-3 py-2 text-sm ${
          message.is_mine ? "bg-slate-900 text-white" : "border border-slate-200 bg-white text-slate-900"
        }`}
      >
        {showSender && !message.is_mine && (
          <p className="mb-0.5 text-xs font-medium text-slate-500">
            {message.sender_name}
            {message.sender_title && <span className="font-normal"> ({message.sender_title})</span>}
          </p>
        )}
        <p className={`whitespace-pre-wrap break-words ${message.is_deleted ? "italic opacity-60" : ""}`}>
          {messageText(message)}
        </p>
        <div className={`mt-1 flex items-center gap-2 text-[11px] ${message.is_mine ? "text-slate-300" : "text-slate-400"}`}>
          <span>{formatJalaliDateTime(message.created_at)}</span>
          {message.can_delete && (
            <button
              type="button"
              onClick={() => onDelete(message)}
              className="underline opacity-0 transition-opacity focus:opacity-100 group-hover:opacity-100"
            >
              حذف
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
