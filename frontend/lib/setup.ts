/**
 * The first-run wizard's logic (Phase 7.6, reshaped for Phase 10's developer account — ADR-010 §A).
 * Pure functions — relative imports only (vitest has no `@/` alias).
 *
 * The server is the authority (it validates everything again, including Django's password rules);
 * these checks only save a round trip and say what is wrong in Persian, next to the field.
 */
import { normalizeNationalCode } from "./login";
import type { SetupStatus } from "./types";

/**
 * Which screen `SignedInWizard` shows, once `Company` exists. "account" (no developer yet) and the
 * "press «شروع راه‌اندازی»" screen (a developer signed in, no company yet) are decided directly by
 * `SetupWizard` from `status.developer_exists` / `status.company_exists`, before this ever runs —
 * this only maps the chart's own bookmark (`Company.setup_step`) to a step once there is a chart.
 */
export type WizardStep = "login" | "company" | "units" | "sections" | "people" | "ready" | "done";

/** The screens in order. `login` is not a step of the chart, only a door. */
export const CHART_STEPS: { key: "company" | "units" | "sections" | "people" | "ready"; title: string }[] = [
  { key: "company", title: "شرکت و حوزه‌ها" },
  { key: "units", title: "واحدها" },
  { key: "sections", title: "بخش‌ها" },
  { key: "people", title: "پرسنل" },
  { key: "ready", title: "آمادهٔ شروع" },
];

/** Why «پایان راه‌اندازی» is still locked, or null when it may run (ADR-010: finishing needs a مدیر
 *  عامل — an active lead on the company root). The server enforces the same rule
 *  (409 `root_lead_missing`); this only disables the button and says why. */
export function finishBlockedReason(status: Pick<SetupStatus, "has_root_lead">): string | null {
  if (status.has_root_lead) return null;
  return "برای پایان راه‌اندازی، دست‌کم یک نفر باید مسئول «خود شرکت» باشد (معمولاً مدیر عامل). او را در مرحلهٔ «پرسنل» ثبت کنید و گزینهٔ «مسئول» را بزنید.";
}

/**
 * Where the wizard should open, from `GET /setup/status/` and whether this browser holds a session.
 * There is no draft state anywhere: every step writes real rows, and `Company.setup_step` is a
 * bookmark, so a refresh, a crash or a different browser all land back here.
 */
export function wizardStepFor(status: SetupStatus, signedIn: boolean): WizardStep {
  if (status.step === "DONE") return "done";
  if (!signedIn) return "login";
  switch (status.step) {
    case "UNITS":
      return "units";
    case "SECTIONS":
      return "sections";
    case "PEOPLE":
      return "people";
    default:
      return "company"; // COMPANY, DOMAINS, or a bookmark we do not know yet
  }
}

/** The developer account, created from the form on a fresh install (no token — removed 2026-09-25,
 *  no company name either — Phase 10 moves that to the wizard's own «شرکت و حوزه‌ها» step). */
export interface AccountForm {
  fullName: string;
  nationalCode: string;
  mobilePhone: string;
  password: string;
  passwordConfirm: string;
}

export const EMPTY_ACCOUNT_FORM: AccountForm = {
  fullName: "",
  nationalCode: "",
  mobilePhone: "",
  password: "",
  passwordConfirm: "",
};

export const PASSWORD_MIN_LENGTH = 8;

export type AccountErrors = Partial<Record<keyof AccountForm, string>>;

/** Client-side checks, in the order the form reads. An empty object means "send it". */
export function validateAccountForm(form: AccountForm): AccountErrors {
  const errors: AccountErrors = {};
  if (!form.fullName.trim()) errors.fullName = "نام و نام خانوادگی را وارد کنید.";
  if (!normalizeNationalCode(form.nationalCode)) errors.nationalCode = "کد ملی را وارد کنید.";
  if (form.password.length < PASSWORD_MIN_LENGTH) {
    errors.password = `رمز عبور باید دست‌کم ${PASSWORD_MIN_LENGTH} نویسه باشد.`;
  } else if (form.passwordConfirm !== form.password) {
    errors.passwordConfirm = "تکرار رمز عبور با رمز عبور یکسان نیست.";
  }
  return errors;
}

/** The `POST /setup/bootstrap/` body. */
export function bootstrapBody(form: AccountForm): Record<string, unknown> {
  return {
    full_name: form.fullName.trim(),
    national_code: normalizeNationalCode(form.nationalCode),
    mobile_phone: form.mobilePhone.trim(),
    password: form.password,
  };
}
