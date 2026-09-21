"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { ApiError, apiPost } from "@/lib/api-client";
import {
  EMPTY_ACCOUNT_FORM,
  SETUP_TOKEN_HEADER,
  bootstrapBody,
  validateAccountForm,
  type AccountErrors,
  type AccountForm,
} from "@/lib/setup";
import type { SetupStatus } from "@/lib/types";
import { DarkError, Field, StepCard, darkInput, primaryButton } from "./ui";

interface BootstrapResponse {
  logged_in: boolean;
}

/**
 * Step 0: the one-time setup token, the company's name, and the مدیر عامل account.
 *
 * The password fields are for a *new* account only. Where an active مدیر عامل already exists the
 * wizard offers to promote them instead: that never sets a password and never signs anyone in, so
 * they continue from the login page with their own password.
 */
export function AccountStep({ status, onDone }: { status: SetupStatus; onDone: () => void }) {
  const [form, setForm] = useState<AccountForm>(EMPTY_ACCOUNT_FORM);
  const [errors, setErrors] = useState<AccountErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [promoted, setPromoted] = useState(false);

  const set = <K extends keyof AccountForm>(key: K, value: AccountForm[K]) => setForm((f) => ({ ...f, [key]: value }));

  async function submit(event: FormEvent) {
    event.preventDefault();
    const found = validateAccountForm(form);
    setErrors(found);
    setServerError(null);
    if (Object.keys(found).length > 0) return;

    setBusy(true);
    try {
      const response = await apiPost<BootstrapResponse>("/setup/bootstrap/", bootstrapBody(form), {
        headers: { [SETUP_TOKEN_HEADER]: form.token.trim() },
      });
      if (response.logged_in) onDone();
      else setPromoted(true);
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "راه‌اندازی ممکن نشد. اتصال را بررسی و دوباره تلاش کنید.");
    } finally {
      setBusy(false);
    }
  }

  if (promoted) {
    return (
      <StepCard title="شرکت ساخته شد" intro="حساب مدیر عامل موجود به ریشهٔ ساختار سازمان افزوده شد.">
        <p className="text-sm leading-7 text-slate-300">
          به دلایل امنیتی با این راه‌اندازی وارد حساب نشدید. با رمز عبور خودتان وارد شوید تا ساختار سازمان را ادامه دهید.
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
      intro="توکن راه‌اندازی را از فایل تنظیمات سرور (VEYE_SETUP_TOKEN) بردارید. پس از پایان کار، آن را از سرور حذف کنید."
    >
      <form onSubmit={submit} className="space-y-5" noValidate>
        {serverError && <DarkError message={serverError} />}

        <Field id="setup-token" label="توکن راه‌اندازی" error={errors.token}>
          <input
            id="setup-token"
            type="password"
            autoComplete="off"
            value={form.token}
            onChange={(e) => set("token", e.target.value)}
            className={`${darkInput} latn text-left`}
          />
        </Field>

        <Field id="company-name" label="نام شرکت" error={errors.companyName}>
          <input
            id="company-name"
            value={form.companyName}
            onChange={(e) => set("companyName", e.target.value)}
            maxLength={255}
            className={darkInput}
          />
        </Field>

        {status.has_users && (
          <fieldset className="space-y-2 rounded-lg border border-line p-4">
            <legend className="px-2 text-sm text-slate-300">مدیر عامل</legend>
            <label className="flex items-center gap-2 text-sm text-slate-200">
              <input type="radio" checked={form.mode === "new"} onChange={() => set("mode", "new")} />
              ساختن حساب تازه
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-200">
              <input type="radio" checked={form.mode === "existing"} onChange={() => set("mode", "existing")} />
              استفاده از حساب مدیر عامل موجود
            </label>
          </fieldset>
        )}

        {form.mode === "new" && (
          <>
            <Field id="full-name" label="نام و نام خانوادگی" error={errors.fullName}>
              <input
                id="full-name"
                value={form.fullName}
                onChange={(e) => set("fullName", e.target.value)}
                maxLength={255}
                className={darkInput}
              />
            </Field>
          </>
        )}

        <Field
          id="national-code"
          label="کد ملی"
          error={errors.nationalCode}
          hint={form.mode === "existing" ? "کد ملی مدیر عاملِ فعالی که از قبل در سامانه هست." : undefined}
        >
          <input
            id="national-code"
            inputMode="numeric"
            autoComplete="username"
            value={form.nationalCode}
            onChange={(e) => set("nationalCode", e.target.value)}
            className={`${darkInput} latn text-left`}
          />
        </Field>

        {form.mode === "new" && (
          <>
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
          </>
        )}

        <button type="submit" disabled={busy} className={`${primaryButton} w-full`}>
          {busy ? "در حال ساخت..." : "ایجاد حساب و ادامه"}
        </button>
      </form>
    </StepCard>
  );
}
