/**
 * Placing people in the chart from the personnel screen (Phase 7.8). Pure functions — relative
 * imports only (vitest has no `@/` alias).
 *
 * Without this no بخش would ever have anyone in it: `/personnel/` creates accounts, and a person is
 * only *in* the organisation once they have a membership.
 */

export interface AssignmentForm {
  /** The node to place the person in; null = "not now". */
  nodeId: number | null;
  /** Mark them مسئول of that node. */
  isLead: boolean;
  positionLabel: string;
}

export const EMPTY_ASSIGNMENT: AssignmentForm = { nodeId: null, isLead: false, positionLabel: "" };

export function hasAssignment(form: AssignmentForm): form is AssignmentForm & { nodeId: number } {
  return form.nodeId !== null;
}

/** The `POST /org/memberships/` body. The person's first membership becomes their primary on the
 *  server, so nothing about "home node" is sent. */
export function membershipBody(userId: number, form: AssignmentForm & { nodeId: number }) {
  return {
    user: userId,
    node: form.nodeId,
    is_lead: form.isLead,
    position_label: form.positionLabel.trim(),
  };
}

export interface RegisterOutcome {
  tone: "success" | "partial";
  message: string;
}

/**
 * What to tell the user after registering a person and (maybe) placing them. A person can be created
 * while the placement fails (an archived node, a permission the server refuses); that must not read
 * as a failure of the whole thing — the account exists — nor be silent.
 */
export function registerOutcome(nodeName: string | null, placementError: string | null): RegisterOutcome {
  if (placementError) {
    return {
      tone: "partial",
      message: `پروفایل پرسنل ثبت شد، اما قرار دادن او در ساختار سازمان ممکن نشد: ${placementError} می‌توانید او را بعداً از «ساختار سازمان» یا فهرست زیر بیفزایید.`,
    };
  }
  return {
    tone: "success",
    message: nodeName
      ? `پروفایل پرسنل با موفقیت ثبت شد و در «${nodeName}» قرار گرفت.`
      : "پروفایل پرسنل با موفقیت ثبت شد.",
  };
}

/** `?unassigned=1`: people with no place in the chart yet, for the «بدون جایگاه» list. */
export const UNASSIGNED_PATH = "/org/people/?unassigned=1&page_size=50";
