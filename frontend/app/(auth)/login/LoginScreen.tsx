"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { apiGet, apiPost, ApiError } from "@/lib/api-client";
import { normalizeNationalCode, safeNextPath } from "@/lib/login";
import type { SetupStatus } from "@/lib/types";
import { ArrowLeft, CircleAlert, Eye, EyeOff, FileCheck2, FolderKanban, IdCard, LockKeyhole, Network } from "lucide-react";
import { AnimatedBackground } from "@/components/ui/AnimatedBackground";
import { BrandMark } from "@/components/ui/BrandMark";
import { buttonClass } from "@/components/ui/Button";
import { navyControlClass } from "@/components/ui/Field";
import { Spinner } from "@/components/ui/Spinner";

const FEATURES = [
  { icon: FileCheck2, text: "هر مستند، از تدوین تا تصویب، با امضا و سوابق کامل" },
  { icon: Network, text: "ساختار سازمان و مسئولان هر بخش، یک‌جا و روشن" },
  { icon: FolderKanban, text: "پروژه‌ها و ریزهدف‌ها با مسئول و مهلت مشخص" },
];

const inputClass = `${navyControlClass} h-11 w-full ps-10`;

const primaryClass = buttonClass({ variant: "glow", size: "lg", className: "group w-full" });

/**
 * Dark, two-column sign-in over the living navy backdrop: the brand on the right (RTL first), a glass card on
 * the left. On a phone the card comes first, under a compact brand mark.
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
    <main className="relative isolate grid min-h-dvh text-slate-100 lg:grid-cols-2">
      <AnimatedBackground />

      <section className="relative hidden flex-col justify-between px-8 py-10 sm:px-14 lg:flex lg:py-16">
        <div className="veye-rise flex items-center gap-3" style={{ "--i": 0 } as React.CSSProperties}>
          <BrandMark size="lg" />
          <span className="text-xl font-extrabold">وی‌آی</span>
        </div>

        <div className="max-w-xl">
          <span
            className="veye-rise mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-slate-300 backdrop-blur"
            style={{ "--i": 1 } as React.CSSProperties}
          >
            <span className="size-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgb(52_211_153/0.8)]" />
            سامانه کنترل مستندات
          </span>
          <h1
            className="veye-rise text-4xl leading-[1.45] font-black"
            style={{ "--i": 2 } as React.CSSProperties}
          >
            سازمان شما،
            <br />
            <span className="bg-gradient-to-l from-sky-300 via-glow to-indigo-300 bg-clip-text text-transparent">
              منظم، کنترل‌شده و قابل‌پیگیری.
            </span>
          </h1>
          <div className="veye-rise veye-rule mt-7 w-40" style={{ "--i": 3 } as React.CSSProperties} aria-hidden />
          <p className="veye-rise mt-7 text-base leading-8 text-slate-400" style={{ "--i": 4 } as React.CSSProperties}>
            سامانهٔ کنترل مستندات و مدیریت کار؛ از تدوین و تصویب مستند تا ساختار سازمان و پروژه‌ها.
          </p>
          <ul className="mt-9 space-y-3.5">
            {FEATURES.map(({ icon: Icon, text }, index) => (
              <li
                key={text}
                className="veye-rise flex items-center gap-3 text-sm text-slate-300"
                style={{ "--i": 5 + index } as React.CSSProperties}
              >
                <span className="flex size-8 shrink-0 items-center justify-center rounded-xl bg-glow/10 text-glow ring-1 ring-inset ring-glow/20">
                  <Icon className="size-4" />
                </span>
                {text}
              </li>
            ))}
          </ul>
        </div>

        <p className="veye-rise text-xs text-slate-500" style={{ "--i": 8 } as React.CSSProperties}>
          وی‌آی · سامانه کنترل مستندات
        </p>
      </section>

      <section className="relative flex min-h-dvh items-center justify-center px-5 py-12 lg:min-h-0">
        <div className="veye-rise w-full max-w-md" style={{ "--i": 2 } as React.CSSProperties}>
          {/* The hero is desktop-only; on a phone the card comes first, under a compact brand mark. */}
          <div className="mb-8 flex items-center justify-center gap-3 lg:hidden">
            <BrandMark />
            <span className="text-lg font-extrabold">وی‌آی</span>
          </div>

          <div className="veye-glass rounded-3xl p-6 sm:p-8">
            {freshWithNoAccounts ? (
              <div className="space-y-6">
                <div>
                  <h2 className="text-2xl font-extrabold">به وی‌آی خوش آمدید</h2>
                  <p className="mt-2 text-sm leading-7 text-slate-400">
                    این سامانه هنوز راه‌اندازی نشده است. با چند مرحلهٔ ساده، حساب توسعه‌دهنده و ساختار سازمان را بسازید.
                  </p>
                </div>
                <Link href="/setup" className={primaryClass}>
                  شروع راه‌اندازی
                  <ArrowLeft className="size-4 transition-transform duration-200 group-hover:-translate-x-1" />
                </Link>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-5">
                <div>
                  <h2 className="text-2xl font-extrabold">ورود به سامانه</h2>
                  <p className="mt-2 text-sm text-slate-400">با کد ملی و رمز عبور خود وارد شوید.</p>
                </div>

                {error && (
                  <div
                    role="alert"
                    className="flex items-start gap-2.5 rounded-xl border border-rose-500/40 bg-rose-500/10 px-3.5 py-2.5 text-sm text-rose-200 animate-fade-in"
                  >
                    <CircleAlert className="mt-0.5 size-4 shrink-0" />
                    {error}
                  </div>
                )}

                <div>
                  <label htmlFor="national-code" className="mb-1.5 block text-sm font-medium text-slate-300">
                    کد ملی
                  </label>
                  <div className="relative">
                    <IdCard aria-hidden className="pointer-events-none absolute inset-y-0 start-3.5 my-auto size-4 text-slate-500" />
                    <input
                      id="national-code"
                      type="text"
                      required
                      inputMode="numeric"
                      autoComplete="username"
                      value={nationalCode}
                      onChange={(e) => setNationalCode(e.target.value)}
                      className={`${inputClass} latn pe-3.5 text-left`}
                    />
                  </div>
                </div>

                <div>
                  <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-slate-300">
                    رمز عبور
                  </label>
                  <div className="relative">
                    <LockKeyhole aria-hidden className="pointer-events-none absolute inset-y-0 start-3.5 my-auto size-4 text-slate-500" />
                    <input
                      id="password"
                      type={showPassword ? "text" : "password"}
                      required
                      autoComplete="current-password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className={`${inputClass} latn pe-10 text-left`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((shown) => !shown)}
                      aria-label={showPassword ? "پنهان کردن رمز" : "نمایش رمز"}
                      aria-pressed={showPassword}
                      title={showPassword ? "پنهان کردن رمز" : "نمایش رمز"}
                      className="absolute inset-y-0 end-1.5 my-auto flex size-8 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-white/5 hover:text-slate-200"
                    >
                      {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                    </button>
                  </div>
                </div>

                <button type="submit" disabled={loading} aria-busy={loading || undefined} className={primaryClass}>
                  {loading && <Spinner />}
                  {loading ? "در حال ورود..." : "ورود"}
                  {!loading && <ArrowLeft className="size-4 transition-transform duration-200 group-hover:-translate-x-1" />}
                </button>

                {setupAvailable && (
                  <p className="border-t border-white/[0.06] pt-5 text-center text-sm leading-7 text-slate-400">
                    ساختار سازمان هنوز تعریف نشده است. با حساب توسعه‌دهنده وارد شوید و «شروع راه‌اندازی» را بزنید.
                  </p>
                )}
              </form>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}
