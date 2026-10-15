/**
 * Choosing your own password (Phase 20): the form's own checks and the server's answer mapped onto
 * its fields. Pure — relative imports only, so vitest can load it.
 */
import { flattenErrorMessages } from "./api-errors";

export interface PasswordForm {
  current: string;
  next: string;
  repeat: string;
}

export const EMPTY_PASSWORD_FORM: PasswordForm = {
  current: "",
  next: "",
  repeat: "",
};

/** Django's shortest accepted password (MinimumLengthValidator); the server checks the rest. */
export const MIN_PASSWORD_LENGTH = 8;

/** What can be said before asking the server, or null. */
export function passwordFormProblem(form: PasswordForm): string | null {
  if (!form.current) return "رمز عبور فعلی را وارد کنید.";
  if (form.next.length < MIN_PASSWORD_LENGTH)
    return `رمز تازه باید دست‌کم ${MIN_PASSWORD_LENGTH.toLocaleString("fa-IR")} نویسه باشد.`;
  if (form.next !== form.repeat) return "تکرار رمز تازه با خود آن یکی نیست.";
  return null;
}

export interface PasswordErrors {
  current?: string;
  next?: string;
  other?: string;
}

/** `POST /auth/password/`'s 400 body (`{current_password: [...]}`, `{new_password: [...]}`, or a detail). */
export function passwordErrors(data: unknown): PasswordErrors {
  if (typeof data !== "object" || data === null) return { other: "تغییر رمز انجام نشد." };
  const body = data as Record<string, unknown>;
  const errors: PasswordErrors = {};
  const current = flattenErrorMessages(body.current_password);
  const next = flattenErrorMessages(body.new_password);
  if (current.length) errors.current = current.join(" ");
  if (next.length) errors.next = next.join(" ");
  if (!errors.current && !errors.next) {
    const rest = flattenErrorMessages(body);
    errors.other = rest.length ? rest.join(" ") : "تغییر رمز انجام نشد.";
  }
  return errors;
}
