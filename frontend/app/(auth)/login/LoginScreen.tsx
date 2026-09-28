"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { apiGet, apiPost, ApiError } from "@/lib/api-client";
import { normalizeNationalCode, safeNextPath } from "@/lib/login";
import type { SetupStatus } from "@/lib/types";
import { ArrowLeft, Eye, EyeOff, IdCard, LockKeyhole } from "lucide-react";
import { BrandMark } from "@/components/ui/BrandMark";
import { Spinner } from "@/components/ui/Spinner";

const FEATURES = [
  "هر مستند، از تدوین تا تصویب، با امضا و سوابق کامل",
  "ساختار سازمان و مسئولان هر بخش، یک‌جا و روشن",
  "پروژه‌ها و ریزهدف‌ها با مسئول و مهلت مشخص",
];

const inputClass =
  "h-11 w-full rounded-xl border border-line bg-surface px-10 text-sm text-slate-100 placeholder:text-slate-500 " +
  "transition-[border-color,box-shadow] duration-150 hover:border-slate-500/60 " +
  "focus:border-accent focus:outline-none focus:ring-4 focus:ring-accent/20";

const primaryClass =
  "group flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-accent px-4 text-sm font-bold text-slate-950 " +
  "shadow-[0_8px_24px_-8px_rgb(56_189_248/0.6)] transition-[background-color,transform,box-shadow] duration-150 " +
  "hover:bg-accent-strong hover:shadow-[0_10px_28px_-8px_rgb(56_189_248/0.75)] active:scale-[0.98] disabled:opacity-60 disabled:active:scale-100";

/**
 * Dark, two-column sign-in: the brand on the right (RTL first), the card on the left.
 *
 * On a database with no developer account yet (`/setup/status/` says `!developer_exists`) the card
 * offers «شروع راه‌اندازی» straight to `/setup`'s account form. Once the developer exists but has not
 * started the company yet, the sign-in form stays and a quiet line says to sign in as them: setup
 * then continues from one button (Phase 10, ADR-010 §A — this used to be the مدیر عامل's job).
 */
export function LoginScreen() {
  const router = useRouter();
  const search = useSearchParams();
  const next = safeNextPath(search.get("next"));

  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [nationalCode, setNationalCode] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
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

  const freshWithNoAccounts = status?.developer_exists === false;
  const setupAvailable = status?.developer_exists === true && status.company_exists === false;

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
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_1px_1px,rgb(148_163_184/0.12)_1px,transparent_0)] bg-[length:26px_26px] [mask-image:linear-gradient(to_bottom,black,transparent_85%)]"
        />
        <div className="veye-rise relative flex items-center gap-3" style={{ "--i": 0 } as React.CSSProperties}>
          <BrandMark size="lg" />
          <span className="text-lg font-bold">وی‌آی</span>
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
            <BrandMark />
            <span className="text-lg font-bold">وی‌آی</span>
          </div>
          {freshWithNoAccounts ? (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold">به وی‌آی خوش آمدید</h2>
                <p className="mt-2 text-sm leading-7 text-slate-400">
                  این سامانه هنوز راه‌اندازی نشده است. با چند مرحلهٔ ساده، حساب توسعه‌دهنده و ساختار سازمان را بسازید.
                </p>
              </div>
              <Link href="/setup" className={primaryClass}>
                شروع راه‌اندازی
                <ArrowLeft className="size-4 transition-transform duration-200 group-hover:-translate-x-0.5" />
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
                  className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-3.5 py-2.5 text-sm text-rose-200 animate-fade-in"
                >
                  {error}
                </div>
              )}

              <div>
                <label htmlFor="national-code" className="mb-1.5 block text-sm font-medium text-slate-300">
                  کد ملی
                </label>
                <div className="relative">
                <IdCard aria-hidden className="pointer-events-none absolute inset-y-0 right-3.5 my-auto size-4 text-slate-500" />
                <input
                  id="national-code"
                  type="text"
                  required
                  inputMode="numeric"
                  autoComplete="username"
                  value={nationalCode}
                  onChange={(e) => setNationalCode(e.target.value)}
                  className={`${inputClass} latn pl-3.5 text-left`}
                />
                </div>
              </div>

              <div>
                <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-slate-300">
                  رمز عبور
                </label>
                <div className="relative">
                <LockKeyhole aria-hidden className="pointer-events-none absolute inset-y-0 right-3.5 my-auto size-4 text-slate-500" />
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={`${inputClass} latn text-left`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((shown) => !shown)}
                  aria-label={showPassword ? "پنهان کردن رمز" : "نمایش رمز"}
                  aria-pressed={showPassword}
                  title={showPassword ? "پنهان کردن رمز" : "نمایش رمز"}
                  className="absolute inset-y-0 left-1.5 my-auto flex size-8 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-white/5 hover:text-slate-200"
                >
                  {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
                </div>
              </div>

              <button type="submit" disabled={loading} aria-busy={loading || undefined} className={primaryClass}>
                {loading && <Spinner />}
                {loading ? "در حال ورود..." : "ورود"}
                {!loading && <ArrowLeft className="size-4 transition-transform duration-200 group-hover:-translate-x-0.5" />}
              </button>

              {setupAvailable && (
                <p className="border-t border-line pt-5 text-center text-sm leading-7 text-slate-400">
                  ساختار سازمان هنوز تعریف نشده است. با حساب توسعه‌دهنده وارد شوید و «شروع راه‌اندازی» را بزنید.
                </p>
              )}
            </form>
          )}
        </div>
      </section>
    </main>
  );
}
