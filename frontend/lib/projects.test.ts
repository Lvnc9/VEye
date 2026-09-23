import { describe, expect, it } from "vitest";
import {
  EMPTY_CREATE_FORM,
  canAddDraftObjective,
  createProjectBody,
  progressBarTone,
  progressLabel,
  validateCreateForm,
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
      objectives: [{ key: "a", title: "  ریزهدف  ", assignee: 5, assigneeName: "علی", due_on: "2026-02-01", weight: 2 }],
    });
    expect(createProjectBody(form)).toEqual({
      section: 7,
      name: "پروژهٔ آزمایشی",
      goal: "هدف",
      starts_on: "2026-01-01",
      due_on: null,
      members: [{ user: 5, role: "MEMBER" }],
      objectives: [{ title: "ریزهدف", assignee: 5, due_on: "2026-02-01", weight: 2 }],
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
  it("needs a title, an assignee and a deadline — no unassigned backlog", () => {
    const base = { title: "کار", assignee: 1, due_on: "2026-01-01" };
    expect(canAddDraftObjective(base)).toBe(true);
    expect(canAddDraftObjective({ ...base, title: "  " })).toBe(false);
    expect(canAddDraftObjective({ ...base, assignee: null })).toBe(false);
    expect(canAddDraftObjective({ ...base, due_on: "" })).toBe(false);
  });
});
