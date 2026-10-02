import { describe, expect, it } from "vitest";
import {
  EMPTY_NC_FILTERS,
  actionCreatePayload,
  actionFormFrom,
  actionPatchPayload,
  closeHint,
  emptyActionForm,
  statusButtons,
  validateActionForm,
  type CorrectiveAction,
  NC_SEVERITY_LABELS,
  NC_SOURCE_LABELS,
  NC_STATUS_LABELS,
  actionsProgress,
  actionsSummary,
  createPayload,
  defaultOwnerNode,
  emptyForm,
  formFromNc,
  hasActiveFilters,
  ncQueryParams,
  patchPayload,
  qualityEventDetail,
  validateNcForm,
  type NonConformance,
  type QualityEvent,
} from "./quality";

const TODAY = "2026-10-02";

function nc(over: Partial<NonConformance> = {}): NonConformance {
  return {
    id: 42,
    code: "NC-0042",
    title: "قطعهٔ معیوب",
    description: "قطعه با نقص تحویل شد",
    source: "INTERNAL",
    source_label: "گزارش داخلی",
    severity: "MAJOR",
    severity_label: "عمده",
    status: "OPEN",
    status_label: "ثبت‌شده، منتظر بررسی",
    owner_node: 7,
    owner_node_name: "RAG",
    reported_by: 3,
    reported_by_name: "گزارش‌دهنده",
    detected_on: "2026-09-30",
    related_document: null,
    related_document_code: null,
    related_document_title: null,
    root_cause: "",
    rejection_reason: "",
    effectiveness_note: "",
    accepted_at: null,
    closed_at: null,
    created_at: "2026-10-01T06:00:00Z",
    actions_total: 0,
    actions_verified: 0,
    actions_overdue: 0,
    can_edit: true,
    can_triage: false,
    can_reopen: false,
    can_add_action: false,
    can_close: false,
    ...over,
  };
}

function event(over: Partial<QualityEvent> = {}): QualityEvent {
  return {
    id: 1,
    kind: "nc_reported",
    kind_label: "عدم‌انطباق ثبت شد",
    nc: 42,
    nc_code: "NC-0042",
    nc_title: "قطعهٔ معیوب",
    actor_name: "مسئول",
    actor_title: "",
    subject_title: "",
    from_status: "",
    to_status: "",
    from_status_label: "",
    to_status_label: "",
    note: "",
    created_at: "2026-10-01T06:00:00Z",
    ...over,
  };
}

describe("vocabulary", () => {
  it("covers every value the server can send", () => {
    expect(Object.keys(NC_STATUS_LABELS)).toEqual(["OPEN", "IN_PROGRESS", "CLOSED", "REJECTED"]);
    expect(Object.keys(NC_SEVERITY_LABELS)).toEqual(["MINOR", "MAJOR", "CRITICAL"]);
    expect(Object.keys(NC_SOURCE_LABELS)).toEqual(["AUDIT", "COMPLAINT", "INSPECTION", "INTERNAL", "OTHER"]);
  });
});

describe("the list's query", () => {
  it("sends only the page when nothing is filtered", () => {
    expect(ncQueryParams(EMPTY_NC_FILTERS, 1, 20)).toEqual({ page: 1, page_size: 20 });
  });

  it("sends only what is set, trimmed — never an empty value the server would read as 'matches nothing'", () => {
    const params = ncQueryParams({ ...EMPTY_NC_FILTERS, q: "  نشت ", status: "IN_PROGRESS", mine: "assigned", overdue: true }, 3, 20);
    expect(params).toEqual({ page: 3, page_size: 20, q: "نشت", status: "IN_PROGRESS", mine: "assigned", overdue: "1" });
    expect("severity" in params).toBe(false);
    expect("source" in params).toBe(false);
  });

  it("knows whether any filter is active", () => {
    expect(hasActiveFilters(EMPTY_NC_FILTERS)).toBe(false);
    expect(hasActiveFilters({ ...EMPTY_NC_FILTERS, q: "   " })).toBe(false);
    expect(hasActiveFilters({ ...EMPTY_NC_FILTERS, overdue: true })).toBe(true);
    expect(hasActiveFilters({ ...EMPTY_NC_FILTERS, severity: "CRITICAL" })).toBe(true);
  });
});

describe("derived action progress", () => {
  it("says 'no actions' rather than 0 of 0", () => {
    expect(actionsSummary(nc())).toBe("بدون اقدام");
    expect(actionsProgress(nc())).toBeNull();
  });

  it("reads «۲ از ۳ اقدام تایید شده» with Persian digits", () => {
    const partly = nc({ actions_total: 3, actions_verified: 2 });
    expect(actionsSummary(partly)).toBe("۲ از ۳ اقدام تایید شده");
    expect(actionsProgress(partly)).toBe(67);
    expect(actionsProgress(nc({ actions_total: 2, actions_verified: 2 }))).toBe(100);
    expect(actionsProgress(nc({ actions_total: 2, actions_verified: 0 }))).toBe(0);
  });
});

describe("the report form", () => {
  it("starts on the reporter's home node", () => {
    expect(defaultOwnerNode(undefined)).toBeNull();
    expect(defaultOwnerNode([])).toBeNull();
    expect(defaultOwnerNode([{ node: 5, is_primary: false }, { node: 9, is_primary: true }])).toBe(9);
    expect(defaultOwnerNode([{ node: 5, is_primary: false }])).toBe(5);
  });

  it("starts empty but dated today, as a minor internal report", () => {
    expect(emptyForm(9, TODAY)).toEqual({
      title: "",
      description: "",
      owner_node: 9,
      source: "INTERNAL",
      severity: "MINOR",
      detected_on: TODAY,
      related_document: null,
    });
  });

  it("asks for what is missing, in Persian, field by field", () => {
    const errors = validateNcForm(emptyForm(null, TODAY), TODAY);
    expect(Object.keys(errors).sort()).toEqual(["description", "owner_node", "title"]);
    expect(validateNcForm({ ...emptyForm(9, TODAY), title: "الف", description: "ب" }, TODAY)).toEqual({});
  });

  it("refuses whitespace as an answer and a date from the future", () => {
    const form = { ...emptyForm(9, TODAY), title: "   ", description: "\n", detected_on: "2026-10-03" };
    const errors = validateNcForm(form, TODAY);
    expect(errors.title).toBeTruthy();
    expect(errors.description).toBeTruthy();
    expect(errors.detected_on).toBe("تاریخ کشف نمی‌تواند در آینده باشد.");
    expect(validateNcForm({ ...form, title: "الف", description: "ب", detected_on: TODAY }, TODAY)).toEqual({});
  });

  it("caps the lengths the server caps", () => {
    const form = { ...emptyForm(9, TODAY), title: "ا".repeat(256), description: "ب".repeat(4001) };
    const errors = validateNcForm(form, TODAY);
    expect(errors.title).toContain("۲۵۵");
    expect(errors.description).toContain("۴۰۰۰");
  });

  it("builds the create body, leaving out an absent document", () => {
    const body = createPayload({ ...emptyForm(9, TODAY), title: " عنوان ", description: " شرح " });
    expect(body).toEqual({ title: "عنوان", description: "شرح", owner_node: 9, source: "INTERNAL", severity: "MINOR", detected_on: TODAY });
    expect("related_document" in body).toBe(false);
    expect(createPayload({ ...emptyForm(9, TODAY), title: "ا", description: "ب", related_document: 12 }).related_document).toBe(12);
  });

  it("builds the edit body from only what changed", () => {
    const record = nc({ related_document: 12 });
    expect(patchPayload(record, formFromNc(record))).toEqual({});
    const edited = { ...formFromNc(record), title: "  عنوان بهتر ", severity: "CRITICAL" as const, related_document: null };
    expect(patchPayload(record, edited)).toEqual({ title: "عنوان بهتر", severity: "CRITICAL", related_document: null });
  });

  it("does not call a trailing space a change", () => {
    const record = nc();
    expect(patchPayload(record, { ...formFromNc(record), title: `${record.title} ` })).toEqual({});
  });
});

describe("a history entry's second line", () => {
  it("shows a status move with the reason when there is one", () => {
    const accepted = event({ kind: "nc_accepted", from_status_label: "ثبت‌شده، منتظر بررسی", to_status_label: "در دست اقدام" });
    expect(qualityEventDetail(accepted)).toBe("ثبت‌شده، منتظر بررسی ← در دست اقدام");
    const reopened = event({ kind: "nc_reopened", from_status_label: "بسته‌شده", to_status_label: "در دست اقدام", note: "مشکل تکرار شد" });
    expect(qualityEventDetail(reopened)).toBe("بسته‌شده ← در دست اقدام — مشکل تکرار شد");
  });

  it("shows a rejection as just its reason", () => {
    const rejected = event({ kind: "nc_rejected", from_status_label: "ثبت‌شده، منتظر بررسی", to_status_label: "ردشده", note: "تکراری است" });
    expect(qualityEventDetail(rejected)).toBe("تکراری است");
  });

  it("shows a moved deadline in Jalali, not as raw ISO", () => {
    const text = qualityEventDetail(event({ kind: "action_due_changed", from_status: "2026-10-03", to_status: "2026-10-20" }));
    expect(text).toContain(" ← ");
    expect(text).not.toContain("2026");
  });

  it("shows an assignment as the note and an unremarkable event as nothing", () => {
    expect(qualityEventDetail(event({ kind: "action_assigned", note: "الف ← ب" }))).toBe("الف ← ب");
    expect(qualityEventDetail(event())).toBe("");
  });
});

// ---------------------------------------------------------------------------
// Corrective actions
// ---------------------------------------------------------------------------

function action(over: Partial<CorrectiveAction> = {}): CorrectiveAction {
  return {
    id: 5,
    nc: 42,
    title: "آموزش تیم",
    description: "دو جلسه",
    assignee: 8,
    assignee_name: "کارگر",
    assignee_title: "کارمند",
    assignee_is_active: true,
    due_on: "2026-10-20",
    status: "TODO",
    status_label: "انجام نشده",
    is_overdue: false,
    completed_at: null,
    verified_by_name: null,
    verified_at: null,
    verification_note: "",
    cancel_reason: "",
    created_at: "2026-10-02T06:00:00Z",
    can_edit: true,
    can_set_status: true,
    can_verify: false,
    can_cancel: true,
    ...over,
  };
}

describe("the status buttons an action offers", () => {
  it("offers exactly the server's graph, forward first", () => {
    expect(statusButtons(action({ status: "TODO" })).map((b) => b.status)).toEqual(["IN_PROGRESS"]);
    expect(statusButtons(action({ status: "IN_PROGRESS" })).map((b) => b.status)).toEqual(["DONE", "TODO"]);
    expect(statusButtons(action({ status: "DONE" })).map((b) => b.status)).toEqual(["IN_PROGRESS"]);
    expect(statusButtons(action({ status: "IN_PROGRESS" })).map((b) => b.forward)).toEqual([true, false]);
  });

  it("never offers a shortcut: no TODO → DONE, and VERIFIED / CANCELLED have their own dialogs", () => {
    const all = (["TODO", "IN_PROGRESS", "DONE", "VERIFIED", "CANCELLED"] as const).flatMap((status) => statusButtons(action({ status })));
    expect(all.map((b) => b.status)).not.toContain("VERIFIED");
    expect(all.map((b) => b.status)).not.toContain("CANCELLED");
    expect(statusButtons(action({ status: "TODO" })).map((b) => b.status)).not.toContain("DONE");
    expect(statusButtons(action({ status: "VERIFIED" }))).toEqual([]);
    expect(statusButtons(action({ status: "CANCELLED" }))).toEqual([]);
  });

  it("offers nothing when the server says the viewer may not move it", () => {
    expect(statusButtons(action({ status: "IN_PROGRESS", can_set_status: false }))).toEqual([]);
  });
});

describe("why a record cannot be closed yet", () => {
  const base = { status: "IN_PROGRESS" as const, can_add_action: true, can_close: false, actions_total: 0, actions_verified: 0 };

  it("says a plan is needed when there are no actions", () => {
    expect(closeHint(base)).toBe("برای بستن، دست‌کم یک اقدام اصلاحی لازم است.");
  });

  it("counts what is still unverified, in Persian digits", () => {
    expect(closeHint({ ...base, actions_total: 3, actions_verified: 1 })).toBe("برای بستن، ۲ اقدام دیگر باید تایید شود.");
  });

  it("says nothing when closing is available", () => {
    expect(closeHint({ ...base, can_close: true, actions_total: 2, actions_verified: 2 })).toBeNull();
  });

  it("says nothing to someone who could not close it anyway, or on a record not being worked", () => {
    expect(closeHint({ ...base, can_add_action: false })).toBeNull();
    expect(closeHint({ ...base, status: "OPEN" })).toBeNull();
    expect(closeHint({ ...base, status: "CLOSED" })).toBeNull();
  });
});

describe("the action form", () => {
  it("asks for what is missing, in Persian", () => {
    const errors = validateActionForm(emptyActionForm(), TODAY);
    expect(Object.keys(errors).sort()).toEqual(["assignee", "due_on", "title"]);
    expect(validateActionForm({ title: "الف", description: "", assignee: 8, due_on: TODAY }, TODAY)).toEqual({});
  });

  it("allows a deadline of today but not the past", () => {
    const form = { title: "الف", description: "", assignee: 8, due_on: "2026-10-01" };
    expect(validateActionForm(form, TODAY).due_on).toBe("مهلت نمی‌تواند در گذشته باشد.");
    expect(validateActionForm({ ...form, due_on: TODAY }, TODAY)).toEqual({});
  });

  it("lets an already-overdue action be edited without being re-dated", () => {
    const overdue = action({ due_on: "2026-09-20" });
    const form = { ...actionFormFrom(overdue), title: "عنوان بهتر" };
    expect(validateActionForm(form, TODAY, overdue)).toEqual({});
    expect(validateActionForm({ ...form, due_on: "2026-09-25" }, TODAY, overdue).due_on).toBeTruthy(); // a *new* past date is still refused
  });

  it("builds the create body trimmed", () => {
    expect(actionCreatePayload({ title: " الف ", description: " ب ", assignee: 8, due_on: TODAY })).toEqual({
      title: "الف",
      description: "ب",
      assignee: 8,
      due_on: TODAY,
    });
  });

  it("builds the edit body from only what changed", () => {
    const current = action();
    expect(actionPatchPayload(current, actionFormFrom(current))).toEqual({});
    expect(actionPatchPayload(current, { ...actionFormFrom(current), assignee: 9, title: " جدید " })).toEqual({ assignee: 9, title: "جدید" });
    expect(actionPatchPayload(current, { ...actionFormFrom(current), title: `${current.title} ` })).toEqual({});
  });
});
