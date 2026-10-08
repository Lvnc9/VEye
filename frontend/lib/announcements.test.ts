import { describe, expect, it } from "vitest";
import {
  BODY_MAX,
  announcementPatchPayload,
  announcementPayload,
  audienceChoices,
  canPublish,
  emptyAnnouncementForm,
  excerpt,
  formFromAnnouncement,
  validateAnnouncementForm,
  type Announcement,
} from "./announcements";

const TODAY = "2026-10-08";

function announcement(over: Partial<Announcement> = {}): Announcement {
  return {
    id: 1, title: "جلسهٔ عمومی", body: "پنجشنبه ساعت ۱۰", author: 3, author_name: "منابع انسانی", author_title: "",
    audience_node: null, audience_name: "همهٔ سازمان", pinned: false, expires_on: null, created_at: "2026-10-08T06:00:00Z",
    edited_at: null, withdrawn_at: null, is_withdrawn: false, is_expired: false, can_manage: true, ...over,
  };
}

const chart = [
  { id: 1, depth: 0, name: "شرکت", is_active: true },
  { id: 2, depth: 1, name: "IT", is_active: true },
  { id: 3, depth: 2, name: "هوش مصنوعی", is_active: true },
  { id: 4, depth: 3, name: "RAG", is_active: true },
  { id: 5, depth: 2, name: "توسعه", is_active: true },
];

describe("who may publish, and to whom", () => {
  it("lets HR and any مسئول publish; nobody else", () => {
    expect(canPublish(true, [])).toBe(true);
    expect(canPublish(false, [{ node: 3, is_lead: true }])).toBe(true);
    expect(canPublish(false, [{ node: 3, is_lead: false }])).toBe(false);
    expect(canPublish(false, undefined)).toBe(false);
  });

  it("offers HR the whole company and every node", () => {
    const choices = audienceChoices(chart, [], true);
    expect(choices.company).toBe(true);
    expect(choices.nodes.map((n) => n.id)).toEqual([1, 2, 3, 4, 5]);
  });

  it("offers a مسئول their node and what is beneath it — never the company", () => {
    const choices = audienceChoices(chart, [{ node: 3, is_lead: true }], false);
    expect(choices.company).toBe(false);
    expect(choices.nodes.map((n) => n.id)).toEqual([3, 4]);
  });
});

describe("the announcement form", () => {
  it("starts company-wide for HR and on the first offered node otherwise", () => {
    expect(emptyAnnouncementForm(true, 3)).toEqual({ title: "", body: "", audience_node: null, pinned: false, expires_on: "" });
    expect(emptyAnnouncementForm(false, 3).audience_node).toBe(3);
  });

  it("asks for a title and text, and refuses an end date in the past", () => {
    const ok = { ...emptyAnnouncementForm(true, null), title: "جلسه", body: "متن" };
    expect(validateAnnouncementForm(ok, TODAY)).toEqual({});
    expect(Object.keys(validateAnnouncementForm(emptyAnnouncementForm(true, null), TODAY)).sort()).toEqual(["body", "title"]);
    expect(validateAnnouncementForm({ ...ok, expires_on: "2026-10-07" }, TODAY).expires_on).toBeTruthy();
    expect(validateAnnouncementForm({ ...ok, expires_on: TODAY }, TODAY)).toEqual({});
    expect(validateAnnouncementForm({ ...ok, body: "x".repeat(BODY_MAX + 1) }, TODAY).body).toBeTruthy();
  });

  it("refuses a past end date only when it is new or changed", () => {
    const old = announcement({ expires_on: "2026-10-01" });
    expect(validateAnnouncementForm(formFromAnnouncement(old), TODAY, old)).toEqual({});
  });

  it("publishes trimmed, with an empty end date as null", () => {
    expect(announcementPayload({ title: " جلسه ", body: " متن ", audience_node: 3, pinned: true, expires_on: "" })).toEqual({
      title: "جلسه", body: "متن", audience_node: 3, pinned: true, expires_on: null,
    });
  });

  it("patches only what changed, never the audience", () => {
    const original = announcement();
    expect(announcementPatchPayload(original, formFromAnnouncement(original))).toEqual({});
    expect(announcementPatchPayload(original, { ...formFromAnnouncement(original), audience_node: 5 })).toEqual({});
    expect(announcementPatchPayload(original, { ...formFromAnnouncement(original), title: "  جلسهٔ عمومی " })).toEqual({});
    expect(announcementPatchPayload(original, { ...formFromAnnouncement(original), pinned: true, expires_on: "2026-10-20" })).toEqual({
      pinned: true, expires_on: "2026-10-20",
    });
  });
});

describe("excerpt", () => {
  it("keeps a short text whole and cuts a long one on a word with an ellipsis", () => {
    expect(excerpt("کوتاه", 20)).toBe("کوتاه");
    expect(excerpt("یک دو سه چهار پنج", 9)).toBe("یک دو سه…");
    expect(excerpt("یک دو سه چهار پنج", 7)).toBe("یک دو…"); // the limit falls inside «سه»: cut before it
    expect(excerpt("  خط\nدوم  ", 50)).toBe("خط دوم"); // a line break folds into a space
  });
});
