/**
 * Company announcements (Phase 19): the vocabulary and pure logic of «اطلاعیه‌ها». No fetching here.
 * Relative imports only (vitest has no `@/` alias).
 */

import { manageableNodes } from "./quality";

export interface Announcement {
  id: number;
  title: string;
  body: string;
  author: number;
  author_name: string;
  author_title: string;
  /** null = the whole company. */
  audience_node: number | null;
  audience_name: string;
  pinned: boolean;
  expires_on: string | null;
  created_at: string;
  edited_at: string | null;
  withdrawn_at: string | null;
  is_withdrawn: boolean;
  is_expired: boolean;
  /** May edit, pin and withdraw it — the rule the endpoints enforce. */
  can_manage: boolean;
}

export const TITLE_MAX = 255;
export const BODY_MAX = 10000;

/** HR (`manage_personnel`) or any مسئول may publish (the server decides to whom). */
export function canPublish(isHr: boolean, memberships: { node: number; is_lead: boolean }[] | undefined): boolean {
  return isHr || Boolean(memberships?.some((m) => m.is_lead));
}

/** Where this person may publish: the whole company and every node for HR; each led node and what is
 *  beneath it for a مسئول — the server's rule (`announcements/access.py`). */
export function audienceChoices<T extends { id: number; depth: number }>(
  nodes: T[],
  memberships: { node: number; is_lead: boolean }[] | undefined,
  isHr: boolean,
): { company: boolean; nodes: T[] } {
  return { company: isHr, nodes: manageableNodes(nodes, memberships, isHr) };
}

export interface AnnouncementForm {
  title: string;
  body: string;
  audience_node: number | null;
  pinned: boolean;
  /** ISO date or "" for none. */
  expires_on: string;
}

export function emptyAnnouncementForm(isHr: boolean, firstNode: number | null): AnnouncementForm {
  return { title: "", body: "", audience_node: isHr ? null : firstNode, pinned: false, expires_on: "" };
}

export function formFromAnnouncement(a: Announcement): AnnouncementForm {
  return { title: a.title, body: a.body, audience_node: a.audience_node, pinned: a.pinned, expires_on: a.expires_on ?? "" };
}

export function validateAnnouncementForm(
  form: AnnouncementForm,
  today: string,
  original?: Pick<Announcement, "expires_on">,
): Partial<Record<keyof AnnouncementForm, string>> {
  const errors: Partial<Record<keyof AnnouncementForm, string>> = {};
  if (!form.title.trim()) errors.title = "عنوان را بنویسید.";
  else if (form.title.trim().length > TITLE_MAX) errors.title = "عنوان بیش از اندازه بلند است.";
  if (!form.body.trim()) errors.body = "متن اطلاعیه را بنویسید.";
  else if (form.body.trim().length > BODY_MAX) errors.body = "متن بیش از اندازه بلند است.";
  if (form.expires_on && form.expires_on < today && form.expires_on !== (original?.expires_on ?? ""))
    errors.expires_on = "تاریخ پایان نمایش نمی‌تواند در گذشته باشد.";
  return errors;
}

export function announcementPayload(form: AnnouncementForm): Record<string, unknown> {
  return {
    title: form.title.trim(),
    body: form.body.trim(),
    audience_node: form.audience_node,
    pinned: form.pinned,
    expires_on: form.expires_on || null,
  };
}

/** Only what changed, and never the audience (fixed once published). */
export function announcementPatchPayload(original: Announcement, form: AnnouncementForm): Record<string, unknown> {
  const before = formFromAnnouncement(original);
  const body: Record<string, unknown> = {};
  if (form.title.trim() !== before.title) body.title = form.title.trim();
  if (form.body.trim() !== before.body) body.body = form.body.trim();
  if (form.pinned !== before.pinned) body.pinned = form.pinned;
  if (form.expires_on !== before.expires_on) body.expires_on = form.expires_on || null;
  return body;
}

/** A one-paragraph preview: whitespace folded, cut on a word with «…» when longer than `max`. */
export function excerpt(text: string, max: number): string {
  const flat = text.replace(/\s+/g, " ").trim();
  if (flat.length <= max) return flat;
  const cut = flat.slice(0, max);
  const lastSpace = cut.lastIndexOf(" ");
  return `${(lastSpace > 0 ? cut.slice(0, lastSpace) : cut).trim()}…`;
}
