"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { ApiError, apiPost } from "@/lib/api-client";
import {
  EMPTY_ACCOUNT_FORM,
  bootstrapBody,
  validateAccountForm,
  type AccountErrors,
  type AccountForm,
} from "@/lib/setup";
import type { SetupStatus } from "@/lib/types";
import { DarkError, Field, StepCard, darkInput, primaryButton } from "./ui";

/**
 * Step 0 for a visitor with no session: the company's name and the first مدیر عامل account — no
 * setup token (removed by the owner, 2026-09-25). If an active مدیر عامل already exists the server
 * refuses a second one from this form, so that person is sent to sign in instead; signed in,
 * SetupWizard's FirstStep gives them StartSetupButton.
 */
export function AccountStep({ status, onDone }: { status: SetupStatus; onDone: () => void }) {
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
      onDone(); // the new account is signed in; the wizard continues under it
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "راه‌اندازی ممکن نشد. اتصال را بررسی و دوباره تلاش کنید.");
    } finally {
      setBusy(false);
    }
  }

  if (status.has_users) {
    return (
      <StepCard title="ورود با حساب مدیر عامل" intro="حساب مدیر عامل از قبل در سامانه هست.">
        <p className="text-sm leading-7 text-slate-300">
          با همان حساب وارد شوید تا با یک کلیک «شروع راه‌اندازی» شرکت را بسازید.
        </p>
        <Link href="/login?next=%2Fsetup" className={`${primaryButton} inline-block`}>
          رفتن به صفحهٔ ورود
        </Link>
      </StepCard>
    );
  }

  return (
    <StepCard
      title="ایجاد حساب مدیر عامل"
      intro="نام شرکت و حساب مدیر عامل را بسازید. پس از آن، ساختار سازمان را گام‌به‌گام تعریف می‌کنید."
    >
      <form onSubmit={submit} className="space-y-5" noValidate>
        {serverError && <DarkError message={serverError} />}

        <Field id="company-name" label="نام شرکت" error={errors.companyName}>
          <input
            id="company-name"
            value={form.companyName}
            onChange={(e) => set("companyName", e.target.value)}
            maxLength={255}
            className={darkInput}
          />
        </Field>

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
