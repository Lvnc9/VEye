/**
 * Shared API types.
 *
 * Domain vocabulary mirrors backend/apps/core/constants.py — keep the two in
 * sync. Persian labels are what users see; the stored values are what the API
 * exchanges.
 */

// ---------------------------------------------------------------------------
// Personnel / RBAC
// ---------------------------------------------------------------------------

export type AccessRoll = "EMPLOYER" | "HEADQUARTERS" | "GUILD";

export type AccessLevel = "L1" | "L2" | "L3";

export const ACCESS_ROLL_LABELS: Record<AccessRoll, string> = {
  EMPLOYER: "کارفرمایی",
  HEADQUARTERS: "ستادی",
  GUILD: "صفی",
};

export const ACCESS_LEVEL_LABELS: Record<AccessLevel, string> = {
  L1: "لول ۱",
  L2: "لول ۲",
  L3: "لول ۳",
};

/**
 * Access Roll x Access Level -> job title.
 * Ported from V_1.0 other_folder/register.py:739-769.
 */
export const TITLE_MATRIX: Record<string, string> = {
  "EMPLOYER:L1": "مدیر عامل",
  "EMPLOYER:L2": "رئیس هیئت مدیره",
  "EMPLOYER:L3": "عضو هیئت مدیره",
  "HEADQUARTERS:L1": "نماینده مدیریت",
  "HEADQUARTERS:L2": "معاون/مشاور",
  "HEADQUARTERS:L3": "مدیر/رئیس",
  "GUILD:L1": "سرپرست",
  "GUILD:L2": "کارشناس",
  "GUILD:L3": "کارمند/اپراتور",
};

export function computeTitle(roll: AccessRoll, level: AccessLevel): string {
  return TITLE_MATRIX[`${roll}:${level}`] ?? "";
}

/**
 * Domain capabilities granted by a user's access roll. Mirrors
 * backend/apps/accounts/models.py Capability.
 *
 * Policy: تدوین -> صفی/ستادی · تایید -> ستادی · تصویب -> کارفرمایی.
 * Use these to hide actions the API would reject anyway — the backend is
 * the enforcement point, this is only for UI affordance.
 */
export type Capability =
  | "create_document"
  | "confirm_document"
  | "approve_document"
  | "manage_personnel"
  | "print_document";

export const CAPABILITY_LABELS: Record<Capability, string> = {
  create_document: "تدوین مستند",
  confirm_document: "تایید مستند",
  approve_document: "تصویب مستند",
  manage_personnel: "مدیریت پرسنل",
  print_document: "ساخت و نمایش PDF مستند",
};

export interface User {
  id: number;
  national_code: string;
  full_name: string;
  mobile_phone: string;
  access_roll: AccessRoll;
  access_level: AccessLevel;
  title: string;
  capabilities: Capability[];
  is_active: boolean;
  date_joined: string;
}

export function hasCapability(user: User | null, capability: Capability): boolean {
  return Boolean(user?.capabilities?.includes(capability));
}

export interface PersonnelWritePayload {
  national_code: string;
  full_name: string;
  mobile_phone?: string;
  access_roll: AccessRoll;
  access_level: AccessLevel;
  password?: string;
}

export interface LoginPayload {
  national_code: string;
  password: string;
}

// ---------------------------------------------------------------------------
// Documents — vocabulary only; the full model lands in Phase 2.
// ---------------------------------------------------------------------------

export type DocumentGroup = "POSTER" | "PROCEDURE" | "INSTRUCTION" | "FORM";

export const DOCUMENT_GROUP_LABELS: Record<DocumentGroup, string> = {
  POSTER: "پوستر",
  PROCEDURE: "روش اجرایی",
  INSTRUCTION: "دستورالعمل",
  FORM: "فرم",
};

/**
 * Group -> document code prefix. Deliberately non-transliterating:
 * روش اجرایی -> PR and دستورالعمل -> WI are crossed in the original and are
 * reproduced literally (V_1.0 other_folder/documents_01.py:699-706).
 */
export const GROUP_CODE_PREFIX: Record<DocumentGroup, string> = {
  POSTER: "PO",
  PROCEDURE: "PR",
  INSTRUCTION: "WI",
  FORM: "FR",
};

export type DocumentCategory = "INSIDE" | "OUTSIDE";

export const DOCUMENT_CATEGORY_LABELS: Record<DocumentCategory, string> = {
  INSIDE: "داخل سازمانی",
  OUTSIDE: "برون سازمانی",
};

export type DocumentStatus =
  | "DRAFT"
  | "AWAITING_CONFIRMATION"
  | "AWAITING_APPROVAL"
  | "UNDER_CONTROL"
  | "OBSOLETE";

export const DOCUMENT_STATUS_LABELS: Record<DocumentStatus, string> = {
  DRAFT: "پیش نویس",
  AWAITING_CONFIRMATION: "در انتظار تأیید",
  AWAITING_APPROVAL: "در انتظار تصویب",
  UNDER_CONTROL: "تحت کنترل",
  OBSOLETE: "منسوخ شده",
};

export type SignOffRole = "creater" | "confirmer" | "approver";

export const SIGN_OFF_ROLE_LABELS: Record<SignOffRole, string> = {
  // "creater" is misspelled in the original throughout — DB field, JSON key
  // and signature filenames all depend on it, so the value is preserved.
  creater: "تدوین کننده",
  confirmer: "تایید کننده",
  approver: "تصویب کننده",
};

// ---------------------------------------------------------------------------
// Document register
// ---------------------------------------------------------------------------

/**
 * The register's per-row action (V_1.0 documents_01.py:886-902): a finalized
 * document is printed, one with a saved body is finished (signed off), and
 * anything else is completed in the designer.
 */
export type DocumentAction = "complete" | "finish" | "print";

export const DOCUMENT_ACTION_LABELS: Record<DocumentAction, string> = {
  complete: "تکمیل",
  finish: "اتمام",
  print: "چاپ",
};

export interface SignOffSummary {
  name: string;
  position: string;
  signed_date: string | null;
}

/** [post, supervisor] — the سمت / ناظر pair of one Responsibilities row. */
export interface ResponsibilityPair {
  post: string;
  supervisor: string;
}

export interface DocumentRow {
  id: number;
  category: DocumentCategory;
  category_label: string;
  title: string;
  group: DocumentGroup;
  group_label: string;
  number: number;
  /** Family code, e.g. "PO-01". */
  code: string;
  revision: number;
  /** Two digits, e.g. "01". */
  revision_display: string;
  /** The printed document number, e.g. "PO-01-01". */
  full_code: string;
  status: DocumentStatus;
  status_label: string;
  action: DocumentAction;
  can_revise: boolean;
  /** True while the document is a draft — the only time its body can change. */
  can_edit: boolean;
  /** null until the designer can assign Responsibilities (Phase 3). */
  responsibilities: {
    accountant: ResponsibilityPair | null;
    questioner: ResponsibilityPair | null;
    responder: ResponsibilityPair | null;
  };
  signoffs: Record<SignOffRole, SignOffSummary | null>;
  /** State of the issued (official) PDF — "none" until the first build. */
  pdf_status: PdfStatus;
  pdf_built_at: string | null;
  /** What the signed-in user can do with this document right now (Phase 5). */
  workflow: WorkflowState;
  /** Why a DRAFT came back (مرجوع). Only on single-document payloads, not register rows. */
  return_note?: ReturnNote | null;
  content_saved_at: string | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Workflow (Phase 5): تدوین → تایید → تصویب, مرجوع, and the public verify page
// ---------------------------------------------------------------------------

export type WorkflowStep = "submit" | "confirm" | "approve";

export interface WorkflowState {
  /** What the status awaits; null when there is nothing to do (or nothing to submit yet). */
  step: WorkflowStep | null;
  can_act: boolean;
  can_return: boolean;
  /** Persian reason when the user holds the capability but signed an earlier step. */
  blocked: string | null;
}

export interface ReturnNote {
  reason: string;
  by: string;
  by_title: string;
  at: string;
}

export type DocumentEventKind = "submitted" | "confirmed" | "approved" | "returned" | "superseded";

export interface DocumentEvent {
  id: number;
  kind: DocumentEventKind;
  kind_label: string;
  from_status: DocumentStatus;
  from_status_label: string;
  to_status: DocumentStatus;
  to_status_label: string;
  actor_name: string;
  actor_title: string;
  reason: string;
  created_at: string;
}

export type VerifyState = "valid" | "obsolete" | "pending";

/** GET /verify/{code}/ — public; a pending document discloses only the first six fields. */
export interface VerifyResult {
  found: true;
  full_code: string;
  revision_display: string;
  state: VerifyState;
  state_label: string;
  message: string;
  title?: string;
  group_label?: string;
  signers?: { role_label: string; name: string; position: string; signed_date: string | null }[];
  current_revision?: { full_code: string; revision_display: string } | null;
}

// ---------------------------------------------------------------------------
// PDF engine (Phase 4)
// ---------------------------------------------------------------------------

/** "official" is the issued PDF of a finalized revision; "preview" is a
 *  watermarked «پیش‌نمایش» of any revision, drafts included. */
export type PdfKind = "official" | "preview";

export type PdfStatus = "none" | "building" | "ready" | "failed";

export interface PdfState {
  kind: PdfKind;
  status: PdfStatus;
  status_label: string;
  requested_at: string | null;
  built_at: string | null;
  size: number | null;
  /** Persian reason for a failed build; empty otherwise. */
  error: string;
  /** A "building" row past the worker's time limit — it can be rebuilt. */
  stale: boolean;
  /** Present while a file exists — even during a rebuild or after a failed one. */
  download_url: string | null;
}

export interface DocumentCreatePayload {
  category: DocumentCategory;
  title: string;
  group: DocumentGroup;
}

export interface DocumentFilters {
  search?: string;
  group?: DocumentGroup | "";
  category?: DocumentCategory | "";
  status?: DocumentStatus | "";
}

// ---------------------------------------------------------------------------
// Document designer
// ---------------------------------------------------------------------------

/** The five block types; the values are V_1.0's own `dynamic_items`
 *  discriminators (other_folder/utils.py:533-655). */
export type SectionType =
  | "Short Explanation"
  | "Long Explanation"
  | "Responsibilities"
  | "Changes Table"
  | "Attachment";

/** The labels of V_1.0's five sidebar buttons (poster_01.py:823-919). */
export const SECTION_TYPE_LABELS: Record<SectionType, string> = {
  "Short Explanation": "تشریحی کوتاه",
  "Long Explanation": "تشریحی بلند",
  Responsibilities: "مسئولیت ها",
  "Changes Table": "جدول تغییرات",
  Attachment: "ضمائم",
};

export const SECTION_TYPES: SectionType[] = [
  "Short Explanation",
  "Long Explanation",
  "Responsibilities",
  "Changes Table",
  "Attachment",
];

/** A document has one of each of these (they feed the register / are joined
 *  across revisions). */
export const SINGLETON_SECTIONS: SectionType[] = ["Responsibilities", "Changes Table"];

export type ResponsibilityRoleKey = "responder" | "receiver" | "cash_account" | "supervisor";

export const RESPONSIBILITY_ROLE_LABELS: Record<ResponsibilityRoleKey, string> = {
  responder: "پاسخگو",
  receiver: "پاسخ‌خواه",
  cash_account: "حسابکش",
  supervisor: "ناظر",
};

export type FileKind = "PICTURE" | "DOCUMENT" | "VIDEO";

export interface DocumentFileInfo {
  id: number;
  name: string;
  kind: FileKind;
  kind_label: string;
  size: number;
  download_url: string;
}

export interface RoleRow {
  role: ResponsibilityRoleKey;
  post: string;
  supervisor: string;
  text: string;
}

export interface ChangeRow {
  /** Absent until the row has been saved once. */
  id?: number;
  text: string;
  /** Set by the server on first save. */
  date?: string;
}

/** A row from an earlier revision's Changes Table — read-only history. */
export interface PreviousChange {
  id: number;
  document_id: number;
  revision: number;
  revision_display: string;
  text: string;
  date: string;
}

export interface AttachmentTarget {
  id: number;
  full_code: string;
  title: string;
  status: DocumentStatus;
  status_label: string;
}

export interface AttachmentItem {
  caption: string;
  /** null until a document has been picked. */
  document: AttachmentTarget | null;
}

interface SectionBase {
  /** Client-only React key; stable across reorders. */
  key: string;
  /** Server id; absent for a block that hasn't been saved yet. */
  id?: number;
}

export interface ShortSection extends SectionBase {
  type: "Short Explanation";
  lines: string[];
}

export interface LongSection extends SectionBase {
  type: "Long Explanation";
  heading: string;
  body: string;
  extra_boxes: string[];
  files: DocumentFileInfo[];
}

export interface ResponsibilitiesSection extends SectionBase {
  type: "Responsibilities";
  roles: RoleRow[];
  notes: string[];
}

export interface ChangesSection extends SectionBase {
  type: "Changes Table";
  rows: ChangeRow[];
}

export interface AttachmentSection extends SectionBase {
  type: "Attachment";
  items: AttachmentItem[];
}

export type DesignerSection =
  | ShortSection
  | LongSection
  | ResponsibilitiesSection
  | ChangesSection
  | AttachmentSection;

/** A section exactly as the API returns it (no client key). */
export type ServerSection = DesignerSection extends infer S
  ? S extends DesignerSection
    ? Omit<S, "key">
    : never
  : never;

export interface ContentResponse {
  document: DocumentRow;
  version: number;
  editable: boolean;
  logo_url: string | null;
  footnote1: string;
  footnote2: string;
  sections: ServerSection[];
  previous_changes: PreviousChange[];
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

export interface StatusVocabularyEntry {
  value: DocumentStatus;
  label: string;
}

export interface DashboardMetricsRow {
  group: string;
  group_value: DocumentGroup;
  counts: Record<DocumentStatus, number>;
  total: number;
}

export interface DashboardMetrics {
  statuses: StatusVocabularyEntry[];
  rows: DashboardMetricsRow[];
}

export interface DashboardSystemInfo {
  total: number;
  by_roll: Partial<Record<AccessRoll, number>>;
  by_level: Partial<Record<AccessLevel, number>>;
}

// ---------------------------------------------------------------------------
// Generic
// ---------------------------------------------------------------------------

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export function unwrapList<T>(payload: T[] | Paginated<T>): T[] {
  return Array.isArray(payload) ? payload : payload.results;
}
