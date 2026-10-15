"use client";

import { useState, type FormEvent } from "react";
import { Eye, EyeOff, KeyRound } from "lucide-react";
import { ApiError, apiPost } from "@/lib/api-client";
import {
  EMPTY_PASSWORD_FORM,
  MIN_PASSWORD_LENGTH,
  passwordErrors,
  passwordFormProblem,
  type PasswordErrors,
  type PasswordForm,
} from "@/lib/password";
import type { User } from "@/lib/types";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field, inputClass } from "@/components/ui/Field";

/**
 * «تغییر رمز عبور» (Phase 20): current, new, repeat. The server signs out every other device and
 * re-issues this browser's cookies, so the person stays here; `onChanged` gets the refreshed user.
 */
export function ChangePasswordForm({ onChanged }: { onChanged: (user: User) => void }) {
  const [form, setForm] = useState<PasswordForm>(EMPTY_PASSWORD_FORM);
  const [visible, setVisible] = useState(false);
  const [errors, setErrors] = useState<PasswordErrors>({});
  const [saving, setSaving] = useState(false);

  const set = (key: keyof PasswordForm) => (value: string) => setForm((current) => ({ ...current, [key]: value }));

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const problem = passwordFormProblem(form);
    if (problem) {
      setErrors({ other: problem });
      return;
    }
    setErrors({});
    setSaving(true);
    try {
      const user = await apiPost<User>("/auth/password/", {
        current_password: form.current,
        new_password: form.next,
      });
      setForm(EMPTY_PASSWORD_FORM);
      onChanged(user);
    } catch (error) {
      setErrors(
        error instanceof ApiError
          ? passwordErrors(error.data ?? { detail: error.message })
          : { other: "تغییر رمز انجام نشد." },
      );
    } finally {
      setSaving(false);
    }
  }

  const type = visible ? "text" : "password";
  return (
    <form onSubmit={submit} className="space-y-4" noValidate>
      <Field label="رمز عبور فعلی" htmlFor="pw-current" error={errors.current} required>
        <input
          id="pw-current"
          type={type}
          autoComplete="current-password"
          dir="ltr"
          value={form.current}
          onChange={(e) => set("current")(e.target.value)}
          aria-invalid={Boolean(errors.current) || undefined}
          className={inputClass}
        />
      </Field>
      <Field
        label="رمز عبور تازه"
        htmlFor="pw-next"
        hint={`دست‌کم ${MIN_PASSWORD_LENGTH.toLocaleString("fa-IR")} نویسه؛ فقط عدد، رایج یا شبیه نام و کد ملی شما نباشد.`}
        error={errors.next}
        required
      >
        <input
          id="pw-next"
          type={type}
          autoComplete="new-password"
          dir="ltr"
          value={form.next}
          onChange={(e) => set("next")(e.target.value)}
          aria-invalid={Boolean(errors.next) || undefined}
          className={inputClass}
        />
      </Field>
      <Field label="تکرار رمز عبور تازه" htmlFor="pw-repeat" required>
        <input
          id="pw-repeat"
          type={type}
          autoComplete="new-password"
          dir="ltr"
          value={form.repeat}
          onChange={(e) => set("repeat")(e.target.value)}
          className={inputClass}
        />
      </Field>
      {errors.other && (
        <Alert tone="danger" role="alert">
          {errors.other}
        </Alert>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button
          variant="ghost"
          size="sm"
          icon={visible ? <EyeOff /> : <Eye />}
          onClick={() => setVisible((v) => !v)}
          aria-pressed={visible}
        >
          {visible ? "پنهان کردن رمزها" : "نمایش رمزها"}
        </Button>
        <Button type="submit" variant="primary" loading={saving} icon={<KeyRound />}>
          تغییر رمز عبور
        </Button>
      </div>
      <p className="text-xs leading-6 text-slate-500">با تغییر رمز، از همهٔ دستگاه‌های دیگر خارج می‌شوید.</p>
    </form>
  );
}
