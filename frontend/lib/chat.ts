/**
 * کارتابل chat (Phase 9): types and pure logic. No fetching — relative imports only (vitest has no
 * `@/` alias). The server decides who may read what; nothing here is a second source of truth.
 */

export type ConversationKind = "DIRECT" | "NODE";
export type MessageKind = "TEXT" | "SYSTEM";

export interface Counterpart {
  id: number;
  full_name: string;
  title: string;
  is_active: boolean;
}

export interface LastMessage {
  id: number;
  kind: MessageKind | null;
  sender_name: string;
  preview: string;
  is_deleted: boolean;
}

export interface Conversation {
  id: number;
  kind: ConversationKind;
  kind_label: string;
  title: string;
  counterpart: Counterpart | null;
  node: number | null;
  node_name: string | null;
  node_kind: string | null;
  is_company_channel: boolean;
  can_post: boolean;
  unread_count: number;
  my_last_read_message_id: number | null;
  last_message: LastMessage | null;
  last_message_at: string | null;
  created_at: string;
}

export interface ChatMessage {
  id: number;
  conversation: number;
  kind: MessageKind;
  sender: number | null;
  sender_name: string;
  sender_title: string;
  body: string;
  is_deleted: boolean;
  is_mine: boolean;
  can_delete: boolean;
  created_at: string;
}

export interface MessagePage {
  results: ChatMessage[];
  has_more: boolean;
}

/** How often an open thread asks `?after=<newest id>` for new messages, and how often the list
 *  (unread counts, ordering) is refreshed. Polling, by the owner's decision — no socket. */
export const THREAD_POLL_MS = 3000;
export const LIST_POLL_MS = 10000;
export const MESSAGE_MAX_LENGTH = 4000;

export const DELETED_TEXT = "پیام حذف شد";
/** Members must be told a group channel is not private (docs/11 §5.3). */
export const NODE_PRIVACY_NOTE = "گفتگوی گروهی — برای مسئولان گره‌های بالادستی نیز قابل مشاهده است.";
export const COMPANY_CHANNEL_NOTE = "گفتگوی همهٔ افراد شرکت";

/** Merge a page of messages into what is on screen: one row per id (a newer copy wins — e.g. a
 *  tombstone replacing the text), oldest first. */
export function mergeMessages(current: ChatMessage[], incoming: ChatMessage[]): ChatMessage[] {
  if (incoming.length === 0) return current;
  const byId = new Map<number, ChatMessage>();
  for (const message of current) byId.set(message.id, message);
  for (const message of incoming) byId.set(message.id, message);
  return [...byId.values()].sort((a, b) => a.id - b.id);
}

export function newestId(messages: ChatMessage[]): number | null {
  return messages.length === 0 ? null : messages[messages.length - 1].id;
}

export function oldestId(messages: ChatMessage[]): number | null {
  return messages.length === 0 ? null : messages[0].id;
}

/** What a bubble shows: a tombstone never shows its words (the server already blanks them). */
export function messageText(message: ChatMessage): string {
  return message.is_deleted ? DELETED_TEXT : message.body;
}

/** The list row's second line. */
export function lastMessageLine(conversation: Conversation): string {
  const last = conversation.last_message;
  if (!last) return "هنوز پیامی نیست";
  const text = last.is_deleted ? DELETED_TEXT : last.preview;
  if (last.kind === "SYSTEM" || !last.sender_name) return text;
  return `${last.sender_name}: ${text}`;
}

/** «۹۹+» past 99; nothing at all for zero. Digits are shaped Persian by the font. */
export function unreadBadge(count: number): string {
  if (count <= 0) return "";
  return count > 99 ? "99+" : String(count);
}

/** The subtitle under a conversation's title. */
export function conversationSubtitle(conversation: Conversation): string {
  if (conversation.kind === "DIRECT") return conversation.counterpart?.title ?? "";
  if (conversation.is_company_channel) return COMPANY_CHANNEL_NOTE;
  return NODE_PRIVACY_NOTE;
}

/** Why the composer is closed, or null when it is open. */
export function readOnlyReason(conversation: Conversation): string | null {
  if (conversation.can_post) return null;
  if (conversation.kind === "DIRECT") return "این شخص غیرفعال است؛ گفتگو فقط‌خواندنی است.";
  return "این گره بایگانی شده است؛ گفتگو فقط‌خواندنی است.";
}

export function canSend(body: string): boolean {
  const text = body.trim();
  return text.length > 0 && text.length <= MESSAGE_MAX_LENGTH;
}

/** Should the read mark move? Only forward, and only when there is something newer than it. */
export function shouldMarkRead(newest: number | null, mark: number | null): boolean {
  return newest !== null && (mark === null || newest > mark);
}

/** The server's own order: most recent activity first, never-used ones last (newest id first). */
export function sortConversations(conversations: Conversation[]): Conversation[] {
  return [...conversations].sort((a, b) => {
    if (a.last_message_at && b.last_message_at) {
      if (a.last_message_at !== b.last_message_at) return a.last_message_at < b.last_message_at ? 1 : -1;
    } else if (a.last_message_at || b.last_message_at) {
      return a.last_message_at ? -1 : 1;
    }
    return b.id - a.id;
  });
}

/** Parse `?c=<id>` — a conversation to open on arrival (the chart's «گفتگو» button lands here). */
export function parseConversationParam(value: string | null): number | null {
  if (!value || !/^\d+$/.test(value)) return null;
  const id = Number(value);
  return id > 0 ? id : null;
}
