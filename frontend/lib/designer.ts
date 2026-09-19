/**
 * The designer's state logic, kept free of React so it can be tested directly:
 * turning a server response into editable state, turning state back into a save
 * payload, and the local checks that mirror the server's validation.
 */
import {
  SINGLETON_SECTIONS,
  type ContentResponse,
  type DesignerSection,
  type ResponsibilityRoleKey,
  type RoleRow,
  type SectionType,
  type ServerSection,
} from "./types";

let keyCounter = 0;
/** A stable React key for a block. (Not crypto.randomUUID: that only exists in
 *  secure contexts, and this must also run over plain http in staging.) */
export function newKey(): string {
  keyCounter += 1;
  return `s${keyCounter}`;
}

/** The four fixed rows, in V_1.0's on-screen order (utils.py:1373-1403). */
export const ROLE_ORDER: ResponsibilityRoleKey[] = ["responder", "receiver", "cash_account", "supervisor"];

export function emptyRoles(): RoleRow[] {
  return ROLE_ORDER.map((role) => ({ role, post: "", supervisor: "", text: "" }));
}

/** A fresh block, with the starting shape V_1.0 gave each type
 *  (poster_01.py:1419-1472). Short Explanation starts with two lines and
 *  Responsibilities with its four rows; V_1.0's two hardcoded demo rows in a new
 *  Changes Table (utils.py:1243-1247) are deliberately not reproduced. */
export function newSection(type: SectionType): DesignerSection {
  const key = newKey();
  switch (type) {
    case "Short Explanation":
      return { key, type, lines: ["", ""] };
    case "Long Explanation":
      return { key, type, heading: "", body: "", extra_boxes: [], files: [] };
    case "Responsibilities":
      return { key, type, roles: emptyRoles(), notes: [] };
    case "Changes Table":
      return { key, type, rows: [] };
    case "Attachment":
      return { key, type, items: [] };
  }
}

export interface DesignerState {
  version: number;
  footnote1: string;
  footnote2: string;
  sections: DesignerSection[];
}

export function withKey(section: ServerSection): DesignerSection {
  return { ...section, key: newKey() } as DesignerSection;
}

/**
 * Editable state from a server response. After a *save*, pass the sections that
 * were just sent as `previous`: the response lists them in the same order, so
 * each keeps its React key. Without that every block would remount on save, and
 * an upload still in flight would finish against a key that no longer exists —
 * its file silently never attaching.
 */
export function fromResponse(response: ContentResponse, previous?: DesignerSection[]): DesignerState {
  const reuse = previous && previous.length === response.sections.length;
  return {
    version: response.version,
    footnote1: response.footnote1,
    footnote2: response.footnote2,
    sections: response.sections.map((section, i) =>
      reuse ? ({ ...section, key: previous[i].key } as DesignerSection) : withKey(section),
    ),
  };
}

export interface SavePayload {
  base_version: number;
  footnote1: string;
  footnote2: string;
  sections: Record<string, unknown>[];
}

/** The body of `PUT /documents/{id}/content/`. */
export function toPayload(state: DesignerState): SavePayload {
  return {
    base_version: state.version,
    footnote1: state.footnote1,
    footnote2: state.footnote2,
    sections: state.sections.map((section) => {
      const id = section.id ?? null;
      switch (section.type) {
        case "Short Explanation":
          return { id, type: section.type, lines: section.lines };
        case "Long Explanation":
          return {
            id,
            type: section.type,
            heading: section.heading,
            body: section.body,
            extra_boxes: section.extra_boxes,
            file_ids: section.files.map((file) => file.id),
          };
        case "Responsibilities":
          return { id, type: section.type, roles: section.roles, notes: section.notes };
        case "Changes Table":
          // The date is the server's; only the id and text travel.
          return { id, type: section.type, rows: section.rows.map(({ id: rowId, text }) => ({ id: rowId ?? null, text })) };
        case "Attachment":
          return {
            id,
            type: section.type,
            items: section.items.map((item) => ({
              caption: item.caption,
              document_id: item.document?.id ?? null,
            })),
          };
      }
    }),
  };
}

/** A stable string for "has anything changed since the last save?" — the
 *  payload minus its version, which only moves on a save. */
export function snapshot(state: DesignerState): string {
  const { base_version: _version, ...rest } = toPayload(state);
  void _version;
  return JSON.stringify(rest);
}

/** Moves a block one place up (-1) or down (+1); a no-op at either end. */
export function moveSection(sections: DesignerSection[], index: number, direction: -1 | 1): DesignerSection[] {
  const target = index + direction;
  if (target < 0 || target >= sections.length) return sections;
  const next = sections.slice();
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

export function canAddSection(sections: DesignerSection[], type: SectionType): boolean {
  return !SINGLETON_SECTIONS.includes(type) || !sections.some((section) => section.type === type);
}

/** Local checks that mirror the server's, so a save that would be rejected is
 *  caught before it is sent. V_1.0 handled an unlinked attachment by silently
 *  dropping it on save (only `all_labels` was serialized, utils.py:623-634). */
export function validate(state: DesignerState): string[] {
  const problems: string[] = [];
  state.sections.forEach((section, index) => {
    const where = `بخش ${index + 1}`;
    if (section.type === "Attachment") {
      section.items.forEach((item, i) => {
        if (!item.caption.trim()) problems.push(`${where}: عنوان ضمیمه ${i + 1} را بنویسید.`);
        if (!item.document) problems.push(`${where}: برای ضمیمه ${i + 1} یک مستند انتخاب کنید.`);
      });
    }
    if (section.type === "Changes Table") {
      section.rows.forEach((row, i) => {
        if (!row.text.trim()) problems.push(`${where}: عنوان تغییر ردیف ${i + 1} را وارد کنید.`);
      });
    }
  });
  return problems;
}
