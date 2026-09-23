import { describe, expect, it } from "vitest";
import {
  DELETED_TEXT,
  MESSAGE_MAX_LENGTH,
  NODE_PRIVACY_NOTE,
  canOpenNodeChannel,
  canSend,
  conversationSubtitle,
  lastMessageLine,
  mergeMessages,
  messageText,
  newestId,
  oldestId,
  parseConversationParam,
  parseInboxTab,
  readOnlyReason,
  shouldMarkRead,
  sortConversations,
  unreadBadge,
  type ChatMessage,
  type Conversation,
} from "./chat";

function msg(id: number, extra: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id,
    conversation: 1,
    kind: "TEXT",
    sender: 1,
    sender_name: "علی",
    sender_title: "",
    body: `پیام ${id}`,
    is_deleted: false,
    is_mine: false,
    can_delete: false,
    created_at: "2026-09-23T10:00:00Z",
    ...extra,
  };
}

function conv(id: number, extra: Partial<Conversation> = {}): Conversation {
  return {
    id,
    kind: "NODE",
    kind_label: "گروهی",
    title: "بخش",
    counterpart: null,
    node: 1,
    node_name: "بخش",
    node_kind: "SECTION",
    is_company_channel: false,
    can_post: true,
    unread_count: 0,
    my_last_read_message_id: null,
    last_message: null,
    last_message_at: null,
    created_at: "2026-09-23T10:00:00Z",
    ...extra,
  };
}

describe("mergeMessages", () => {
  it("keeps one row per id, oldest first, a newer copy winning", () => {
    const merged = mergeMessages([msg(1), msg(3)], [msg(2), msg(3, { is_deleted: true, body: "" })]);
    expect(merged.map((m) => m.id)).toEqual([1, 2, 3]);
    expect(merged[2].is_deleted).toBe(true);
  });

  it("returns the same array when nothing arrived (no re-render churn)", () => {
    const current = [msg(1)];
    expect(mergeMessages(current, [])).toBe(current);
  });

  it("prepends an older page", () => {
    expect(mergeMessages([msg(5), msg(6)], [msg(3), msg(4)]).map((m) => m.id)).toEqual([3, 4, 5, 6]);
  });
});

describe("cursors", () => {
  it("reads the newest and oldest ids", () => {
    expect(newestId([msg(1), msg(9)])).toBe(9);
    expect(oldestId([msg(1), msg(9)])).toBe(1);
    expect(newestId([])).toBeNull();
    expect(oldestId([])).toBeNull();
  });
});

describe("texts", () => {
  it("never shows a tombstone's words", () => {
    expect(messageText(msg(1, { is_deleted: true, body: "" }))).toBe(DELETED_TEXT);
    expect(messageText(msg(1))).toBe("پیام 1");
  });

  it("builds the list's second line", () => {
    expect(lastMessageLine(conv(1))).toBe("هنوز پیامی نیست");
    const last = { id: 5, kind: "TEXT" as const, sender_name: "علی", preview: "سلام", is_deleted: false };
    expect(lastMessageLine(conv(1, { last_message: last }))).toBe("علی: سلام");
    expect(lastMessageLine(conv(1, { last_message: { ...last, is_deleted: true, preview: "" } }))).toBe(`علی: ${DELETED_TEXT}`);
    expect(lastMessageLine(conv(1, { last_message: { ...last, kind: "SYSTEM", sender_name: "" } }))).toBe("سلام");
  });

  it("caps the unread badge and hides zero", () => {
    expect(unreadBadge(0)).toBe("");
    expect(unreadBadge(7)).toBe("7");
    expect(unreadBadge(100)).toBe("99+");
  });

  it("labels a group channel as visible to leads above", () => {
    expect(conversationSubtitle(conv(1))).toBe(NODE_PRIVACY_NOTE);
    expect(conversationSubtitle(conv(1, { is_company_channel: true }))).not.toBe(NODE_PRIVACY_NOTE);
    const counterpart = { id: 2, full_name: "سارا", title: "کارشناس", is_active: true };
    expect(conversationSubtitle(conv(1, { kind: "DIRECT", counterpart }))).toBe("کارشناس");
  });

  it("explains a closed composer", () => {
    expect(readOnlyReason(conv(1))).toBeNull();
    expect(readOnlyReason(conv(1, { can_post: false }))).toContain("بایگانی");
    expect(readOnlyReason(conv(1, { kind: "DIRECT", can_post: false }))).toContain("غیرفعال");
  });
});

describe("rules", () => {
  it("sends only non-blank text within the limit", () => {
    expect(canSend("  ")).toBe(false);
    expect(canSend(" سلام ")).toBe(true);
    expect(canSend("x".repeat(MESSAGE_MAX_LENGTH))).toBe(true);
    expect(canSend("x".repeat(MESSAGE_MAX_LENGTH + 1))).toBe(false);
  });

  it("moves the read mark only forward", () => {
    expect(shouldMarkRead(null, null)).toBe(false);
    expect(shouldMarkRead(5, null)).toBe(true);
    expect(shouldMarkRead(5, 5)).toBe(false);
    expect(shouldMarkRead(6, 5)).toBe(true);
    expect(shouldMarkRead(4, 5)).toBe(false);
  });

  it("orders like the server: recent activity first, unused last", () => {
    const list = [
      conv(1),
      conv(2, { last_message_at: "2026-09-01T00:00:00Z" }),
      conv(3, { last_message_at: "2026-09-02T00:00:00Z" }),
      conv(4),
    ];
    expect(sortConversations(list).map((c) => c.id)).toEqual([3, 2, 4, 1]);
  });

  it("parses the ?c= parameter strictly", () => {
    expect(parseConversationParam("12")).toBe(12);
    for (const bad of [null, "", "0", "-3", "1.5", "abc", "12x"]) expect(parseConversationParam(bad)).toBeNull();
  });
});

describe("inbox tab and chart affordance", () => {
  it("defaults to conversations", () => {
    expect(parseInboxTab("awaiting")).toBe("awaiting");
    for (const other of [null, "", "x", "conversations"]) expect(parseInboxTab(other)).toBe("conversations");
  });

  it("mirrors the server's channel rule", () => {
    const section = { id: 5, kind: "SECTION" };
    const ancestors = [1, 2, 3]; // company, domain, unit
    expect(canOpenNodeChannel(section, ancestors, [{ node: 5, is_lead: false }])).toBe(true); // member
    expect(canOpenNodeChannel(section, ancestors, [{ node: 3, is_lead: true }])).toBe(true); // lead above
    expect(canOpenNodeChannel(section, ancestors, [{ node: 3, is_lead: false }])).toBe(false); // member above, not lead
    expect(canOpenNodeChannel(section, ancestors, [{ node: 9, is_lead: true }])).toBe(false); // lead elsewhere
    expect(canOpenNodeChannel({ id: 1, kind: "COMPANY" }, [], [{ node: 9, is_lead: false }])).toBe(true);
    expect(canOpenNodeChannel({ id: 1, kind: "COMPANY" }, [], [])).toBe(false);
  });
});
