/**
 * Projects (Phase 8): types and pure logic. Pure functions, no fetching — relative imports only
 * (vitest has no `@/` alias).
 */

export type ProjectStatus = "ACTIVE" | "ON_HOLD" | "DONE" | "CANCELLED";
export type ProjectRole = "MANAGER" | "MEMBER";
export type ObjectiveStatus = "TODO" | "IN_PROGRESS" | "BLOCKED" | "DONE" | "CANCELLED";

export const PROJECT_STATUS_LABELS: Record<ProjectStatus, string> = {
  ACTIVE: "در حال اجرا",
  ON_HOLD: "متوقف",
  DONE: "پایان‌یافته",
  CANCELLED: "لغو شده",
};

export const PROJECT_STATUS_TONE: Record<ProjectStatus, string> = {
  ACTIVE: "bg-green-100 text-green-800",
  ON_HOLD: "bg-amber-100 text-amber-800",
  DONE: "bg-slate-200 text-slate-700",
  CANCELLED: "bg-red-100 text-red-800",
};

export const OBJECTIVE_STATUS_LABELS: Record<ObjectiveStatus, string> = {
  TODO: "انجام نشده",
  IN_PROGRESS: "در حال انجام",
  BLOCKED: "متوقف",
  DONE: "انجام شد",
  CANCELLED: "لغو شد",
};

export const OBJECTIVE_STATUS_TONE: Record<ObjectiveStatus, string> = {
  TODO: "bg-slate-100 text-slate-700",
  IN_PROGRESS: "bg-blue-100 text-blue-800",
  BLOCKED: "bg-amber-100 text-amber-800",
  DONE: "bg-green-100 text-green-800",
  CANCELLED: "bg-red-100 text-red-800",
};

export const PROJECT_ROLE_LABELS: Record<ProjectRole, string> = {
  MANAGER: "مدیر پروژه",
  MEMBER: "عضو",
};

/** Tailwind classes per project-activity-event kind — the direct analogue of
 *  `lib/history.ts`'s `EVENT_KIND_TONE` for the document register. */
export const PROJECT_EVENT_TONE: Record<string, string> = {
  project_created: "bg-blue-500",
  project_status_changed: "bg-amber-500",
  project_archived: "bg-slate-400",
  project_unarchived: "bg-green-600",
  member_added: "bg-teal-500",
  guest_invited: "bg-violet-400",
  member_role_changed: "bg-amber-500",
  member_removed: "bg-red-500",
  objective_added: "bg-blue-500",
  objective_assigned: "bg-teal-500",
  objective_status_changed: "bg-amber-500",
  objective_due_changed: "bg-orange-500",
  objective_removed: "bg-red-500",
  comment_added: "bg-slate-400",
  comment_removed: "bg-red-500",
  document_linked: "bg-green-600",
  document_unlinked: "bg-red-500",
};

export interface ProjectMemberPreview {
  user: number;
  name: string;
  role: ProjectRole;
  is_guest: boolean;
}

export interface ProjectMember {
  id: number;
  user: number;
  user_name: string;
  user_title: string;
  role: ProjectRole;
  role_label: string;
  is_guest: boolean;
}

export interface Project {
  id: number;
  name: string;
  goal: string;
  section: number;
  section_name: string;
  status: ProjectStatus;
  status_label: string;
  starts_on: string | null;
  due_on: string | null;
  is_archived: boolean;
  archived_at: string | null;
  created_at: string;
  my_role: ProjectRole | null;
  can_edit: boolean;
  member_count: number;
  members_preview: ProjectMemberPreview[];
  progress: number | null;
  weight_done: number;
  weight_total: number;
  objective_count: number;
  overdue_count: number;
}

export interface ProjectDetail extends Project {
  members: ProjectMember[];
}

export interface Objective {
  id: number;
  position: number;
  title: string;
  description: string;
  assignee: number;
  assignee_name: string;
  due_on: string;
  status: ObjectiveStatus;
  status_label: string;
  weight: number;
  completed_at: string | null;
  is_overdue: boolean;
  can_edit: boolean;
  can_change_status: boolean;
}

export interface ProjectComment {
  id: number;
  objective: number | null;
  author: number | null;
  author_name: string;
  author_title: string;
  body: string;
  created_at: string;
  can_delete: boolean;
}

export interface ProjectDocumentLink {
  id: number;
  document: number;
  document_full_code: string;
  document_title: string;
  caption: string;
  linked_by_name: string;
  created_at: string;
}

export interface ProjectActivityEvent {
  id: number;
  project: { id: number; name: string };
  objective: { id: number; title: string } | null;
  kind: string;
  kind_label: string;
  from_status: string;
  from_status_label: string;
  to_status: string;
  to_status_label: string;
  actor_name: string;
  actor_title: string;
  subject_title: string;
  note: string;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Progress and overdue tint — presentation-only mirrors of the backend's own
// derived numbers (queries.py); nothing here is a second source of truth.
// ---------------------------------------------------------------------------

/** «٪۲۵» (percent sign first, RTL reading order), or «بدون ریزهدف» while there is nothing to
 *  measure — `progress` is `null`, not `0`, exactly so this distinction can be drawn. */
export function progressLabel(progress: number | null): string {
  return progress === null ? "بدون ریزهدف" : `٪${progress}`;
}

/** Tailwind classes for the progress bar's fill, by how far along it is. */
export function progressBarTone(progress: number | null): string {
  if (progress === null) return "bg-slate-200";
  if (progress >= 100) return "bg-green-600";
  if (progress >= 50) return "bg-sky-600";
  return "bg-amber-500";
}

// ---------------------------------------------------------------------------
// Create form — one page, submitted as one POST with nested members/objectives
// (docs/11 §3.5): a half-created project must not be reachable.
// ---------------------------------------------------------------------------

export interface DraftMember {
  user: number;
  name: string;
  title: string;
  role: ProjectRole;
}

export interface DraftObjective {
  /** A client-side key for React's list rendering — real ids do not exist until submission. */
  key: string;
  title: string;
  assignee: number | null;
  assigneeName: string;
  due_on: string;
  weight: number;
}

export interface ProjectCreateForm {
  section: number | null;
  name: string;
  goal: string;
  starts_on: string;
  due_on: string;
  members: DraftMember[];
  objectives: DraftObjective[];
}

export const EMPTY_CREATE_FORM: ProjectCreateForm = {
  section: null,
  name: "",
  goal: "",
  starts_on: "",
  due_on: "",
  members: [],
  objectives: [],
};

export type CreateErrors = Partial<Record<"section" | "name" | "due_on", string>>;

export function validateCreateForm(form: ProjectCreateForm): CreateErrors {
  const errors: CreateErrors = {};
  if (!form.section) errors.section = "بخش را انتخاب کنید.";
  if (!form.name.trim()) errors.name = "نام پروژه را وارد کنید.";
  if (form.starts_on && form.due_on && form.due_on < form.starts_on) {
    errors.due_on = "مهلت پروژه نمی‌تواند پیش از تاریخ شروع آن باشد.";
  }
  return errors;
}

/** The `POST /projects/` body — one request, so a half-created project cannot exist. */
export function createProjectBody(form: ProjectCreateForm) {
  return {
    section: form.section,
    name: form.name.trim(),
    goal: form.goal.trim(),
    starts_on: form.starts_on || null,
    due_on: form.due_on || null,
    members: form.members.map((m) => ({ user: m.user, role: m.role })),
    objectives: form.objectives.map((o) => ({
      title: o.title.trim(),
      assignee: o.assignee,
      due_on: o.due_on,
      weight: o.weight,
    })),
  };
}

/** A ریز هدف draft is addable once it has a title, an assignee and a deadline — both required,
 *  no unassigned backlog (docs/11 §2.4). */
export function canAddDraftObjective(draft: { title: string; assignee: number | null; due_on: string }): boolean {
  return draft.title.trim().length > 0 && draft.assignee !== null && draft.due_on.length > 0;
}
