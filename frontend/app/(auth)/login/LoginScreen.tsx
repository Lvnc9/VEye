"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { apiGet, apiPost, ApiError } from "@/lib/api-client";
import { normalizeNationalCode, safeNextPath } from "@/lib/login";
import type { SetupStatus } from "@/lib/types";

const FEATURES = [
  "هر مستند، از تدوین تا تصویب، با امضا و سوابق کامل",
  "ساختار سازمان و مسئولان هر بخش، یک‌جا و روشن",
  "پروژه‌ها و ریزهدف‌ها با مسئول و مهلت مشخص",
];

const inputClass =
  "w-full rounded-lg border border-line bg-surface px-3.5 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 " +
  "focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30";

/**
 * Dark, two-column sign-in: the brand on the right (RTL first), the card on the left.
 *
 * On a database with no company yet (`/setup/status/` says `needed`) the card offers «شروع راه‌اندازی».
 * If an active مدیر عامل account already exists (an install that predates setup, or the importer),
 * the sign-in form stays — otherwise that install would be locked out — and setup is a quiet link.
 */
export function LoginScreen() {
  const router = useRouter();
  const search = useSearchParams();
  const next = safeNextPath(search.get("next"));

  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [nationalCode, setNationalCode] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    apiGet<SetupStatus>("/setup/status/")
      .then((s) => !cancelled && setStatus(s))
      .catch(() => {
        /* the form is the safe default: an unreachable status must never hide it */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const freshWithNoAccounts = status?.needed === true && !status.has_users;
  const setupAvailable = status?.needed === true && status.has_users;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await apiPost("/auth/login/", { national_code: normalizeNationalCode(nationalCode), password });
      router.push(next);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "ورود ممکن نشد. اتصال خود را بررسی کنید و دوباره تلاش کنید.",
      );
      setLoading(false);
    }
  }

  return (
    <main className="grid min-h-screen bg-surface text-slate-100 lg:grid-cols-2">
      <section className="relative hidden flex-col justify-between overflow-hidden px-8 py-10 sm:px-14 lg:flex lg:py-16">
        <div
          aria-hidden
          className="pointer-events-none absolute -top-40 -right-40 h-[28rem] w-[28rem] rounded-full bg-accent/10 blur-3xl"
        />
        <div className="veye-rise relative flex items-center gap-3" style={{ "--i": 0 } as React.CSSProperties}>
          <span className="flex h-11 w-11 items-center justify-center rounded-xl border border-line bg-surface-raised text-xl font-bold text-accent">
            وی
          </span>
          <span className="text-lg font-bold tracking-tight">وی‌آی</span>
        </div>

        <div className="relative my-14 max-w-xl lg:my-0">
          <h1
            className="veye-rise text-3xl leading-[1.5] font-bold sm:text-4xl sm:leading-[1.5]"
            style={{ "--i": 1 } as React.CSSProperties}
          >
            سازمان شما،
            <br />
            <span className="text-accent">منظم، کنترل‌شده و قابل‌پیگیری.</span>
          </h1>
          <div className="veye-rise veye-rule mt-6 w-40" style={{ "--i": 2 } as React.CSSProperties} aria-hidden />
          <p className="veye-rise mt-6 text-base leading-8 text-slate-400" style={{ "--i": 3 } as React.CSSProperties}>
            سامانهٔ کنترل مستندات و مدیریت کار؛ از تدوین و تصویب مستند تا ساختار سازمان و پروژه‌ها.
          </p>
          <ul className="mt-8 space-y-3 text-sm text-slate-300">
            {FEATURES.map((feature, index) => (
              <li
                key={feature}
                className="veye-rise flex items-start gap-3"
                style={{ "--i": 4 + index } as React.CSSProperties}
              >
                <span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                {feature}
              </li>
            ))}
          </ul>
        </div>

        <p className="veye-rise relative text-xs text-slate-500" style={{ "--i": 7 } as React.CSSProperties}>
          وی‌آی · سامانه کنترل مستندات
        </p>
      </section>

      <section className="flex min-h-screen items-center justify-center border-line bg-surface-raised px-6 py-12 lg:min-h-0 lg:border-r">
        <div className="veye-rise w-full max-w-sm" style={{ "--i": 2 } as React.CSSProperties}>
          {/* The hero is desktop-only; on a phone the form comes first, under a compact brand mark. */}
          <div className="mb-10 flex items-center gap-3 lg:hidden">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-line bg-surface text-lg font-bold text-accent">
              وی
            </span>
            <span className="text-lg font-bold tracking-tight">وی‌آی</span>
          </div>
          {freshWithNoAccounts ? (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold">به وی‌آی خوش آمدید</h2>
                <p className="mt-2 text-sm leading-7 text-slate-400">
                  این سامانه هنوز راه‌اندازی نشده است. با چند مرحلهٔ ساده، حساب مدیر عامل و ساختار سازمان خود را بسازید.
                </p>
              </div>
              <Link
                href="/setup"
                className="block w-full rounded-lg bg-accent px-4 py-3 text-center text-sm font-bold text-slate-950 transition-colors hover:bg-accent-strong"
              >
                شروع راه‌اندازی
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <h2 className="text-2xl font-bold">ورود به سامانه</h2>
                <p className="mt-2 text-sm text-slate-400">با کد ملی و رمز عبور خود وارد شوید.</p>
              </div>

              {error && (
                <div
                  role="alert"
                  className="rounded-lg border border-red-500/40 bg-red-500/10 px-3.5 py-2.5 text-sm text-red-200"
                >
                  {error}
                </div>
              )}

              <div>
                <label htmlFor="national-code" className="mb-1.5 block text-sm font-medium text-slate-300">
                  کد ملی
                </label>
                <input
                  id="national-code"
                  type="text"
                  required
                  inputMode="numeric"
                  autoComplete="username"
                  value={nationalCode}
                  onChange={(e) => setNationalCode(e.target.value)}
                  className={`${inputClass} latn text-left`}
                />
              </div>

              <div>
                <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-slate-300">
                  رمز عبور
                </label>
                <input
                  id="password"
                  type="password"
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={`${inputClass} latn text-left`}
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-lg bg-accent px-4 py-3 text-sm font-bold text-slate-950 transition-colors hover:bg-accent-strong disabled:opacity-50"
              >
                {loading ? "در حال ورود..." : "ورود"}
              </button>

              {setupAvailable && (
                <p className="border-t border-line pt-5 text-center text-sm text-slate-400">
                  ساختار سازمان هنوز تعریف نشده است.{" "}
                  <Link href="/setup" className="font-medium text-accent hover:underline">
                    راه‌اندازی شرکت
                  </Link>
                </p>
              )}
            </form>
          )}
        </div>
      </section>
    </main>
  );
}
