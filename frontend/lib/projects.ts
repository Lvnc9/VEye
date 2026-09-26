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
/** Feed kinds whose `to_status` carries the meeting's day as an ISO date (backend `_meeting_event`). */
export const MEETING_EVENT_KINDS: ReadonlySet<string> = new Set(["meeting_scheduled", "meeting_changed", "meeting_cancelled"]);

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
  objective_update_added: "bg-sky-500",
  meeting_scheduled: "bg-indigo-500",
  meeting_changed: "bg-amber-500",
  meeting_cancelled: "bg-red-500",
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
  /** Role MANAGER, and the project is not archived — gates the meeting create/edit/delete form. */
  can_manage_meetings: boolean;
}

/** The one entry shown inline on an assignee leaf, or a row of the paged «سوابق». `can_edit` here is
 *  per-update — true only for its own author, and only on their latest entry on the objective. */
export interface ObjectiveUpdateSummary {
  id: number;
  body: string;
  created_at: string;
  edited_at: string | null;
  can_edit: boolean;
}

/** A row of `GET …/objectives/{oid}/updates/` — the same shape plus who wrote it, since that
 *  endpoint is not scoped to one assignee's leaf the way `Objective.assignees[].latest_update` is. */
export interface ObjectiveUpdate {
  id: number;
  author: number | null;
  author_name: string;
  author_title: string;
  body: string;
  created_at: string;
  edited_at: string | null;
  can_edit: boolean;
}

export interface ObjectiveAssignee {
  user: number;
  name: string;
  title: string;
  latest_update: ObjectiveUpdateSummary | null;
  update_count: number;
}

export interface Objective {
  id: number;
  position: number;
  title: string;
  description: string;
  assignees: ObjectiveAssignee[];
  due_on: string;
  status: ObjectiveStatus;
  status_label: string;
  weight: number;
  completed_at: string | null;
  is_overdue: boolean;
  /** Manager or lead. Covers title, description, due date, weight, assignees, delete and reorder. */
  can_edit: boolean;
  /** `can_edit`, or the viewer is one of the assignees. */
  can_change_status: boolean;
  /** The viewer is an assignee and the project is not archived. */
  can_post_update: boolean;
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

export interface MeetingAttendee {
  member: number;
  user: number;
  name: string;
  acknowledged_at: string | null;
}

export interface ProjectMeeting {
  id: number;
  title: string;
  held_on: string;
  start_time: string | null;
  location: string;
  description: string;
  created_by_name: string;
  created_at: string;
  attendees: MeetingAttendee[];
  attendee_count: number;
  acknowledged_count: number;
  /** `null` while the viewer hasn't pressed «مشاهده شد» — also `null` for someone who isn't an attendee. */
  my_acknowledged_at: string | null;
  /** The viewer is an invited attendee who hasn't acknowledged yet. */
  can_acknowledge: boolean;
  /** This particular meeting may still be edited/deleted — role MANAGER and the project not archived. */
  can_edit: boolean;
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
  assignees: number[];
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
      assignees: o.assignees,
      due_on: o.due_on,
      weight: o.weight,
    })),
  };
}

/** A ریزهدف draft is addable once it has a title, at least one assignee and a deadline — all
 *  required, no unassigned backlog (docs/11 §2.4). */
export function canAddDraftObjective(draft: { title: string; assignees: number[]; due_on: string }): boolean {
  return draft.title.trim().length > 0 && draft.assignees.length > 0 && draft.due_on.length > 0;
}

/** Bug fix (docs/12 §D): changing the بخش, or removing a member in `MemberPicker`, must not leave a
 *  draft objective pointing at someone who is no longer a candidate member. Pure so the page's effect
 *  can call it without re-deriving the rule. */
export function pruneOrphanAssignees(objectives: DraftObjective[], memberIds: ReadonlySet<number>): DraftObjective[] {
  return objectives.map((o) => ({ ...o, assignees: o.assignees.filter((id) => memberIds.has(id)) }));
}

// ---------------------------------------------------------------------------
// Objective tree (Phase 10 §D): shaping an Objective's assignees into the leaf
// view-models ObjectiveTree.tsx renders — kept pure so it is testable without React.
// ---------------------------------------------------------------------------

export interface ObjectiveAssigneeRow {
  user: number;
  name: string;
  title: string;
  /** The signed-in user is this assignee. */
  isSelf: boolean;
  latestUpdate: ObjectiveUpdateSummary | null;
  /** Entries besides the one already shown as `latestUpdate` — the count on «سوابق (n)». */
  historyCount: number;
  /** Show «نوشتن گزارش»: it's you, and the objective/project allow it right now. */
  canPostUpdate: boolean;
  /** Show «ویرایش» on the latest entry: it's you, and it is still your latest one. */
  canEditLatest: boolean;
}

/** One row per assignee, in the order the server sent them. */
export function objectiveAssigneeRows(objective: Objective, currentUserId: number | null): ObjectiveAssigneeRow[] {
  return objective.assignees.map((assignee) => {
    const isSelf = currentUserId !== null && assignee.user === currentUserId;
    return {
      user: assignee.user,
      name: assignee.name,
      title: assignee.title,
      isSelf,
      latestUpdate: assignee.latest_update,
      historyCount: Math.max(0, assignee.update_count - (assignee.latest_update ? 1 : 0)),
      canPostUpdate: isSelf && objective.can_post_update,
      canEditLatest: isSelf && Boolean(assignee.latest_update?.can_edit),
    };
  });
}

/** «سوابق» loads every one of an assignee's updates (newest first, same as `latest_update`) — drop
 *  the row that duplicates what the leaf already shows above the expander. */
export function olderUpdates(rows: ObjectiveUpdate[], latestId: number | undefined): ObjectiveUpdate[] {
  return rows.filter((row) => row.id !== latestId);
}

// ---------------------------------------------------------------------------
// Server-side project draft (docs/12 §D): one per user, autosaved from
// /projects/new. The payload is opaque to the server, so its shape and
// versioning live entirely here.
// ---------------------------------------------------------------------------

export const PROJECT_DRAFT_VERSION = 1;

export interface ProjectDraftPayload {
  version: number;
  form: ProjectCreateForm;
}

/** The `PUT /projects/draft/` body: the contract wraps the opaque payload as `{payload: …}` (a bare
 *  `{version, form}` is a 400). `GET` answers `{payload, updated_at}`; feed its `payload` to
 *  `parseDraftPayload`. */
export function serializeDraft(form: ProjectCreateForm): { payload: ProjectDraftPayload } {
  return { payload: { version: PROJECT_DRAFT_VERSION, form } };
}

/** `null` for anything that isn't a recognised, well-shaped draft: no draft saved yet, a version this
 *  build doesn't know (ignored per the contract, not shown as broken), or a payload that doesn't even
 *  look like a `ProjectCreateForm`. Scalar fields default from `EMPTY_CREATE_FORM` so a payload that
 *  predates a field addition still loads. */
export function parseDraftPayload(payload: unknown): ProjectCreateForm | null {
  if (!payload || typeof payload !== "object") return null;
  const { version, form } = payload as { version?: unknown; form?: unknown };
  if (version !== PROJECT_DRAFT_VERSION) return null;
  if (!form || typeof form !== "object") return null;
  const candidate = form as Partial<ProjectCreateForm>;
  if (!Array.isArray(candidate.members) || !Array.isArray(candidate.objectives)) return null;
  return { ...EMPTY_CREATE_FORM, ...candidate };
}

/** The `PATCH …/objectives/{oid}/` body for the edit dialog: `assignees` always replaces the set. */
export function editObjectiveBody(form: {
  title: string;
  description: string;
  assignees: number[];
  due_on: string;
  weight: number;
}) {
  return {
    title: form.title.trim(),
    description: form.description.trim(),
    assignees: form.assignees,
    due_on: form.due_on,
    weight: form.weight,
  };
}

// ---------------------------------------------------------------------------
// Meetings (Phase 10 §D): «جدول جلسات» and acknowledgement.
// ---------------------------------------------------------------------------

/** The `POST`/`PATCH …/meetings/…` body. `start_time`/`location`/`description` are optional on the
 *  wire — an empty string becomes `null` for the time (the API's `TimeField`) and stays `""` for the
 *  two text fields (the API's `blank=True` `CharField`s). */
export function meetingBody(form: {
  title: string;
  held_on: string;
  start_time: string;
  location: string;
  description: string;
  attendees: number[];
}) {
  return {
    title: form.title.trim(),
    held_on: form.held_on,
    start_time: form.start_time || null,
    location: form.location.trim(),
    description: form.description.trim(),
    attendees: form.attendees,
  };
}

/** «اعضای متوجه‌شده» / «هنوز ندیده‌اند», in the order the server sent the attendees. */
export function splitAcknowledgement(attendees: MeetingAttendee[]): {
  acknowledged: MeetingAttendee[];
  pending: MeetingAttendee[];
} {
  return {
    acknowledged: attendees.filter((a) => a.acknowledged_at !== null),
    pending: attendees.filter((a) => a.acknowledged_at === null),
  };
}
