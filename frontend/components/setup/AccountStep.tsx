"use client";

import { useState, type FormEvent } from "react";
import { ApiError, apiPost } from "@/lib/api-client";
import {
  EMPTY_ACCOUNT_FORM,
  bootstrapBody,
  validateAccountForm,
  type AccountErrors,
  type AccountForm,
} from "@/lib/setup";
import { DarkError, Field, StepCard, darkInput, primaryButton } from "./ui";

/**
 * The developer account's form (Phase 10, ADR-010 §A) — no setup token (removed 2026-09-25), and no
 * company name here either: the developer creates the company afterwards with one press
 * («شروع راه‌اندازی»), and names it in the wizard's own «شرکت و حوزه‌ها» step. `SetupWizard` renders
 * this only while `status.developer_exists` is false, so there is nothing to check here about who
 * else might already exist.
 */
export function AccountStep({ onDone }: { onDone: () => void }) {
  const [form, setForm] = useState<AccountForm>(EMPTY_ACCOUNT_FORM);
  const [errors, setErrors] = useState<AccountErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const set = <K extends keyof AccountForm>(key: K, value: AccountForm[K]) => setForm((f) => ({ ...f, [key]: value }));

  async function submit(event: FormEvent) {
    event.preventDefault();
    const found = validateAccountForm(form);
    setErrors(found);
    setServerError(null);
    if (Object.keys(found).length > 0) return;

    setBusy(true);
    try {
      await apiPost("/setup/bootstrap/", bootstrapBody(form));
      onDone(); // the new developer account is signed in; the wizard continues under it
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "راه‌اندازی ممکن نشد. اتصال را بررسی و دوباره تلاش کنید.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <StepCard
      title="ایجاد حساب توسعه‌دهنده"
      intro="حساب توسعه‌دهنده، یک حساب فنی برای راه‌اندازی اولیه است: در نمودار سازمان نیست و سندی امضا نمی‌کند. پس از این حساب، ساختار سازمان را گام‌به‌گام تعریف می‌کنید و در پایان، مدیر عامل را به‌عنوان پرسنل ثبت می‌کنید."
    >
      <form onSubmit={submit} className="space-y-5" noValidate>
        {serverError && <DarkError message={serverError} />}

        <Field id="full-name" label="نام و نام خانوادگی" error={errors.fullName}>
          <input
            id="full-name"
            value={form.fullName}
            onChange={(e) => set("fullName", e.target.value)}
            maxLength={255}
            className={darkInput}
          />
        </Field>

        <Field id="national-code" label="کد ملی" error={errors.nationalCode}>
          <input
            id="national-code"
            inputMode="numeric"
            autoComplete="username"
            value={form.nationalCode}
            onChange={(e) => set("nationalCode", e.target.value)}
            className={`${darkInput} latn text-left`}
          />
        </Field>

        <Field id="mobile" label="تلفن همراه (اختیاری)">
          <input
            id="mobile"
            inputMode="tel"
            value={form.mobilePhone}
            onChange={(e) => set("mobilePhone", e.target.value)}
            className={`${darkInput} latn text-left`}
          />
        </Field>

        <Field id="password" label="رمز عبور" error={errors.password} hint="دست‌کم ۸ نویسه؛ رایج یا فقط عدد نباشد.">
          <input
            id="password"
            type="password"
            autoComplete="new-password"
            value={form.password}
            onChange={(e) => set("password", e.target.value)}
            className={`${darkInput} latn text-left`}
          />
        </Field>

        <Field id="password-confirm" label="تکرار رمز عبور" error={errors.passwordConfirm}>
          <input
            id="password-confirm"
            type="password"
            autoComplete="new-password"
            value={form.passwordConfirm}
            onChange={(e) => set("passwordConfirm", e.target.value)}
            className={`${darkInput} latn text-left`}
          />
        </Field>

        <button type="submit" disabled={busy} className={`${primaryButton} w-full`}>
          {busy ? "در حال ساخت..." : "ایجاد حساب و ادامه"}
        </button>
      </form>
    </StepCard>
  );
}
