import { describe, expect, it } from "vitest";
import {
  EMPTY_CREATE_FORM,
  canAddDraftObjective,
  createProjectBody,
  editObjectiveBody,
  meetingBody,
  objectiveAssigneeRows,
  olderUpdates,
  parseDraftPayload,
  progressBarTone,
  progressLabel,
  pruneOrphanAssignees,
  serializeDraft,
  splitAcknowledgement,
  validateCreateForm,
  type DraftObjective,
  type MeetingAttendee,
  type Objective,
  type ObjectiveUpdate,
  type ProjectCreateForm,
} from "./projects";

describe("progressLabel", () => {
  it("shows the percent sign first, RTL reading order", () => {
    expect(progressLabel(25)).toBe("٪25");
    expect(progressLabel(0)).toBe("٪0");
    expect(progressLabel(100)).toBe("٪100");
  });

  it("distinguishes null (no plan yet) from zero (a plan with nothing done)", () => {
    expect(progressLabel(null)).toBe("بدون ریزهدف");
    expect(progressLabel(null)).not.toBe(progressLabel(0));
  });
});

describe("progressBarTone", () => {
  it("colours by how far along the project is", () => {
    expect(progressBarTone(null)).toContain("slate");
    expect(progressBarTone(10)).toContain("amber");
    expect(progressBarTone(49)).toContain("amber");
    expect(progressBarTone(50)).toContain("sky");
    expect(progressBarTone(99)).toContain("sky");
    expect(progressBarTone(100)).toContain("green");
  });
});

const filled = (over: Partial<ProjectCreateForm> = {}): ProjectCreateForm => ({
  ...EMPTY_CREATE_FORM,
  section: 7,
  name: "  پروژهٔ آزمایشی  ",
  ...over,
});

describe("validateCreateForm", () => {
  it("accepts a minimal valid form (goal, dates, members and objectives are all optional)", () => {
    expect(validateCreateForm(filled())).toEqual({});
  });

  it("requires a section and a name", () => {
    expect(validateCreateForm(EMPTY_CREATE_FORM)).toEqual({
      section: "بخش را انتخاب کنید.",
      name: "نام پروژه را وارد کنید.",
    });
    expect(validateCreateForm(filled({ name: "   " })).name).toBeTruthy();
  });

  it("refuses a deadline before the start date", () => {
    const errors = validateCreateForm(filled({ starts_on: "2026-06-01", due_on: "2026-05-01" }));
    expect(errors.due_on).toBeTruthy();
  });

  it("allows a due date with no start date and vice versa", () => {
    expect(validateCreateForm(filled({ due_on: "2026-05-01" }))).toEqual({});
    expect(validateCreateForm(filled({ starts_on: "2026-05-01" }))).toEqual({});
  });
});

describe("createProjectBody", () => {
  it("trims text, sends null for empty dates, and maps members/objectives to their API shape", () => {
    const form = filled({
      goal: "  هدف  ",
      starts_on: "2026-01-01",
      members: [{ user: 5, name: "علی", title: "کارشناس", role: "MEMBER" }],
      objectives: [{ key: "a", title: "  ریزهدف  ", assignees: [5, 9], due_on: "2026-02-01", weight: 2 }],
    });
    expect(createProjectBody(form)).toEqual({
      section: 7,
      name: "پروژهٔ آزمایشی",
      goal: "هدف",
      starts_on: "2026-01-01",
      due_on: null,
      members: [{ user: 5, role: "MEMBER" }],
      objectives: [{ title: "ریزهدف", assignees: [5, 9], due_on: "2026-02-01", weight: 2 }],
    });
  });

  it("sends empty arrays for a project with no members or plan yet", () => {
    expect(createProjectBody(filled())).toEqual({
      section: 7,
      name: "پروژهٔ آزمایشی",
      goal: "",
      starts_on: null,
      due_on: null,
      members: [],
      objectives: [],
    });
  });
});

describe("canAddDraftObjective", () => {
  it("needs a title, at least one assignee and a deadline — no unassigned backlog", () => {
    const base = { title: "کار", assignees: [1], due_on: "2026-01-01" };
    expect(canAddDraftObjective(base)).toBe(true);
    expect(canAddDraftObjective({ ...base, title: "  " })).toBe(false);
    expect(canAddDraftObjective({ ...base, assignees: [] })).toBe(false);
    expect(canAddDraftObjective({ ...base, due_on: "" })).toBe(false);
  });

  it("accepts several assignees", () => {
    expect(canAddDraftObjective({ title: "کار", assignees: [1, 2, 3], due_on: "2026-01-01" })).toBe(true);
  });
});

const draftObjective = (over: Partial<DraftObjective> = {}): DraftObjective => ({
  key: "a",
  title: "کار",
  assignees: [1, 2],
  due_on: "2026-01-01",
  weight: 1,
  ...over,
});

describe("pruneOrphanAssignees", () => {
  it("drops assignees who are no longer candidate members", () => {
    const pruned = pruneOrphanAssignees([draftObjective({ assignees: [1, 2, 3] })], new Set([1, 3]));
    expect(pruned[0].assignees).toEqual([1, 3]);
  });

  it("leaves an objective with no valid assignee left empty, not dropped", () => {
    const pruned = pruneOrphanAssignees([draftObjective({ assignees: [2] })], new Set([1]));
    expect(pruned).toHaveLength(1);
    expect(pruned[0].assignees).toEqual([]);
  });

  it("changes nothing when every assignee is still a candidate", () => {
    const objectives = [draftObjective({ assignees: [1, 2] })];
    expect(pruneOrphanAssignees(objectives, new Set([1, 2, 3]))).toEqual(objectives);
  });
});

describe("serializeDraft / parseDraftPayload", () => {
  it("round-trips a form through the current version", () => {
    const form = filled({ objectives: [draftObjective()] });
    expect(parseDraftPayload(serializeDraft(form).payload)).toEqual(form);
  });

  it("wraps the payload the way PUT /projects/draft/ expects", () => {
    expect(Object.keys(serializeDraft(filled()))).toEqual(["payload"]);
    expect(serializeDraft(filled()).payload.version).toBe(1);
  });

  it("ignores an unknown version rather than treating it as corrupt", () => {
    expect(parseDraftPayload({ version: 2, form: filled() })).toBeNull();
  });

  it("ignores null, non-objects and malformed payloads", () => {
    expect(parseDraftPayload(null)).toBeNull();
    expect(parseDraftPayload("not an object")).toBeNull();
    expect(parseDraftPayload({ version: 1 })).toBeNull();
    expect(parseDraftPayload({ version: 1, form: { members: "not an array", objectives: [] } })).toBeNull();
  });

  it("fills in missing scalar fields from the empty form (forward compatibility)", () => {
    const parsed = parseDraftPayload({ version: 1, form: { members: [], objectives: [] } });
    expect(parsed).toEqual(EMPTY_CREATE_FORM);
  });
});

const objective = (over: Partial<Objective> = {}): Objective => ({
  id: 1,
  position: 0,
  title: "ریزهدف",
  description: "",
  assignees: [],
  due_on: "2026-05-01",
  status: "TODO",
  status_label: "انجام نشده",
  weight: 1,
  completed_at: null,
  is_overdue: false,
  can_edit: false,
  can_change_status: false,
  can_post_update: false,
  ...over,
});

describe("objectiveAssigneeRows", () => {
  it("shapes each assignee into a leaf row, in the server's order", () => {
    const rows = objectiveAssigneeRows(
      objective({
        can_post_update: true,
        assignees: [
          { user: 7, name: "علی", title: "کارشناس", latest_update: null, update_count: 0 },
          {
            user: 9,
            name: "رضا",
            title: "مدیر",
            latest_update: { id: 3, body: "شروع شد", created_at: "2026-05-01T10:00:00Z", edited_at: null, can_edit: true },
            update_count: 4,
          },
        ],
      }),
      7,
    );
    expect(rows.map((r) => r.user)).toEqual([7, 9]);
    expect(rows[0]).toMatchObject({ isSelf: true, latestUpdate: null, historyCount: 0, canPostUpdate: true, canEditLatest: false });
    expect(rows[1]).toMatchObject({ isSelf: false, historyCount: 3, canPostUpdate: false, canEditLatest: false });
  });

  it("only offers edit/post to the assignee who is the signed-in user, and only for their own latest entry", () => {
    const rows = objectiveAssigneeRows(
      objective({
        can_post_update: true,
        assignees: [
          {
            user: 7,
            name: "علی",
            title: "کارشناس",
            latest_update: { id: 3, body: "شروع شد", created_at: "2026-05-01T10:00:00Z", edited_at: null, can_edit: true },
            update_count: 1,
          },
        ],
      }),
      7,
    );
    expect(rows[0].canPostUpdate).toBe(true);
    expect(rows[0].canEditLatest).toBe(true);
  });

  it("never offers edit/post when can_post_update is false, even for the viewer's own leaf", () => {
    const rows = objectiveAssigneeRows(
      objective({
        can_post_update: false,
        assignees: [{ user: 7, name: "علی", title: "کارشناس", latest_update: null, update_count: 0 }],
      }),
      7,
    );
    expect(rows[0].canPostUpdate).toBe(false);
  });

  it("treats a null current user as nobody's leaf", () => {
    const rows = objectiveAssigneeRows(
      objective({ assignees: [{ user: 7, name: "علی", title: "کارشناس", latest_update: null, update_count: 0 }] }),
      null,
    );
    expect(rows[0].isSelf).toBe(false);
  });
});

const update = (over: Partial<ObjectiveUpdate> = {}): ObjectiveUpdate => ({
  id: 1,
  author: 7,
  author_name: "علی",
  author_title: "کارشناس",
  body: "متن",
  created_at: "2026-05-01T10:00:00Z",
  edited_at: null,
  can_edit: false,
  ...over,
});

describe("olderUpdates", () => {
  it("drops the row already shown as the leaf's latest update", () => {
    const rows = [update({ id: 3 }), update({ id: 2 }), update({ id: 1 })];
    expect(olderUpdates(rows, 3).map((r) => r.id)).toEqual([2, 1]);
  });

  it("keeps every row when nothing matches (e.g. the leaf had no latest update)", () => {
    const rows = [update({ id: 2 }), update({ id: 1 })];
    expect(olderUpdates(rows, undefined).map((r) => r.id)).toEqual([2, 1]);
  });
});

describe("editObjectiveBody", () => {
  it("trims text and sends the assignee id set as-is", () => {
    expect(
      editObjectiveBody({ title: "  عنوان  ", description: "  شرح  ", assignees: [7, 9], due_on: "2026-05-01", weight: 3 }),
    ).toEqual({ title: "عنوان", description: "شرح", assignees: [7, 9], due_on: "2026-05-01", weight: 3 });
  });
});

describe("meetingBody", () => {
  it("trims text, sends null for an empty time, and keeps blank text fields blank", () => {
    expect(
      meetingBody({
        title: "  جلسهٔ هفتگی  ",
        held_on: "2026-05-01",
        start_time: "",
        location: "  ",
        description: "  ",
        attendees: [1, 2],
      }),
    ).toEqual({ title: "جلسهٔ هفتگی", held_on: "2026-05-01", start_time: null, location: "", description: "", attendees: [1, 2] });
  });

  it("keeps a given time and location as-is (trimmed)", () => {
    expect(
      meetingBody({ title: "جلسه", held_on: "2026-05-01", start_time: "10:30", location: "  اتاق ۱  ", description: "", attendees: [] }),
    ).toMatchObject({ start_time: "10:30", location: "اتاق ۱" });
  });
});

const attendee = (over: Partial<MeetingAttendee> = {}): MeetingAttendee => ({
  member: 1,
  user: 1,
  name: "علی",
  acknowledged_at: null,
  ...over,
});

describe("splitAcknowledgement", () => {
  it("splits attendees into acknowledged and pending, keeping the server's order within each", () => {
    const attendees = [
      attendee({ member: 1, acknowledged_at: "2026-05-02T00:00:00Z" }),
      attendee({ member: 2, acknowledged_at: null }),
      attendee({ member: 3, acknowledged_at: "2026-05-03T00:00:00Z" }),
    ];
    const { acknowledged, pending } = splitAcknowledgement(attendees);
    expect(acknowledged.map((a) => a.member)).toEqual([1, 3]);
    expect(pending.map((a) => a.member)).toEqual([2]);
  });

  it("handles every attendee already acknowledged, or none at all", () => {
    expect(splitAcknowledgement([attendee({ acknowledged_at: "2026-05-02T00:00:00Z" })]).pending).toEqual([]);
    expect(splitAcknowledgement([attendee({ acknowledged_at: null })]).acknowledged).toEqual([]);
    expect(splitAcknowledgement([])).toEqual({ acknowledged: [], pending: [] });
  });
});
