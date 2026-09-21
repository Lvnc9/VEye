/**
 * The first-run wizard's logic (Phase 7.6): which screen to show, and what to check before sending.
 * Pure functions — relative imports only (vitest has no `@/` alias).
 *
 * The server is the authority (it validates everything again, including Django's password rules);
 * these checks only save a round trip and say what is wrong in Persian, next to the field.
 */
import { normalizeNationalCode } from "./login";
import type { SetupStatus } from "./types";

export type WizardStep = "account" | "login" | "company" | "units" | "sections" | "ready" | "done";

/** The screens in order; `login` and `done` are not steps of the chart, only doors. */
export const CHART_STEPS: { key: "company" | "units" | "sections" | "ready"; title: string }[] = [
  { key: "company", title: "شرکت و حوزه‌ها" },
  { key: "units", title: "واحدها" },
  { key: "sections", title: "بخش‌ها" },
  { key: "ready", title: "آمادهٔ شروع" },
];

/**
 * Where the wizard should open, from `GET /setup/status/` and whether this browser holds a session.
 * There is no draft state anywhere: every step writes real rows, and `Company.setup_step` is a
 * bookmark, so a refresh, a crash or a different browser all land back here.
 */
export function wizardStepFor(status: SetupStatus, signedIn: boolean): WizardStep {
  if (status.needed) return "account";
  if (status.step === "DONE") return "done";
  if (!signedIn) return "login";
  switch (status.step) {
    case "UNITS":
      return "units";
    case "SECTIONS":
      return "sections";
    case "PEOPLE":
      return "ready";
    default:
      return "company"; // COMPANY, DOMAINS, or a bookmark we do not know yet
  }
}

export interface AccountForm {
  token: string;
  companyName: string;
  /** Create a new مدیر عامل, or promote an active one that already exists. */
  mode: "new" | "existing";
  fullName: string;
  nationalCode: string;
  mobilePhone: string;
  password: string;
  passwordConfirm: string;
}

export const EMPTY_ACCOUNT_FORM: AccountForm = {
  token: "",
  companyName: "",
  mode: "new",
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
  if (!form.token.trim()) errors.token = "توکن راه‌اندازی را وارد کنید.";
  if (!form.companyName.trim()) errors.companyName = "نام شرکت را وارد کنید.";
  if (!normalizeNationalCode(form.nationalCode)) errors.nationalCode = "کد ملی را وارد کنید.";

  if (form.mode === "new") {
    if (!form.fullName.trim()) errors.fullName = "نام و نام خانوادگی را وارد کنید.";
    if (form.password.length < PASSWORD_MIN_LENGTH) {
      errors.password = `رمز عبور باید دست‌کم ${PASSWORD_MIN_LENGTH} نویسه باشد.`;
    } else if (form.passwordConfirm !== form.password) {
      errors.passwordConfirm = "تکرار رمز عبور با رمز عبور یکسان نیست.";
    }
  }
  return errors;
}

/** The `POST /setup/bootstrap/` body. The token travels in a header, never here. */
export function bootstrapBody(form: AccountForm): Record<string, unknown> {
  const companyName = form.companyName.trim();
  const nationalCode = normalizeNationalCode(form.nationalCode);
  if (form.mode === "existing") {
    return { company_name: companyName, existing_manager_national_code: nationalCode };
  }
  return {
    company_name: companyName,
    manager: {
      full_name: form.fullName.trim(),
      national_code: nationalCode,
      mobile_phone: form.mobilePhone.trim(),
      password: form.password,
    },
  };
}

/** The header the backend reads the one-time setup token from (see backend setup_views.py). */
export const SETUP_TOKEN_HEADER = "X-VEYE-Setup-Token";
