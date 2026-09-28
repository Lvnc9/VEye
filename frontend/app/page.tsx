"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiGet, apiGetIfSignedIn } from "@/lib/api-client";
import type { SetupStatus, User } from "@/lib/types";
import { BrandMark } from "@/components/ui/BrandMark";

/**
 * The public landing page (Phase 10, ADR-010 §A). `/` used to be authenticated-only (an instant
 * redirect to /dashboard; proxy.ts sent anyone else to /login first) — it is public now, and decides
 * from `GET /setup/status/` alone what a fresh visitor needs: build the **one** developer account,
 * sign in as that developer to continue setup, or — once setup is finished — go straight into the
 * app (signed in) or to the sign-in form.
 */
export default function Home() {
  const router = useRouter();
  const [status, setStatus] = useState<SetupStatus | null | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    apiGet<SetupStatus>("/setup/status/")
      .then((s) => !cancelled && setStatus(s))
      .catch(() => !cancelled && setStatus(null));
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!status?.completed) return;
    let cancelled = false;
    // The session check must not bounce an anonymous visitor to /login — this page decides that.
    apiGetIfSignedIn<User>("/auth/me/").then((user) => {
      if (!cancelled) router.replace(user ? "/dashboard" : "/login");
    });
    return () => {
      cancelled = true;
    };
  }, [status, router]);

  if (status === undefined || status?.completed) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-surface">
        <p className="text-sm text-slate-500">در حال بارگذاری...</p>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-surface px-6 py-12 text-slate-100">
      <div className="veye-rise w-full max-w-md text-center" style={{ "--i": 0 } as React.CSSProperties}>
        <div className="mb-8 flex items-center justify-center gap-3">
          <BrandMark size="lg" />
          <span className="text-lg font-bold">وی‌آی</span>
        </div>

        <h1 className="text-2xl leading-[1.5] font-bold sm:text-3xl">
          سازمان شما،
          <br />
          <span className="text-accent">منظم، کنترل‌شده و قابل‌پیگیری.</span>
        </h1>

        {status === null ? (
          <>
            <p className="mt-4 text-sm leading-7 text-slate-400">دریافت وضعیت سامانه ممکن نشد. اتصال خود را بررسی کنید.</p>
            <Link
              href="/login"
              className="mt-8 inline-block w-full rounded-xl border border-line px-5 py-3 text-sm font-bold text-slate-200 transition-colors hover:bg-white/5 sm:w-auto"
            >
              ورود به سامانه
            </Link>
          </>
        ) : !status.developer_exists ? (
          <>
            <p className="mt-4 text-sm leading-7 text-slate-400">
              این سامانه هنوز راه‌اندازی نشده است. با چند مرحلهٔ ساده، حساب توسعه‌دهنده و ساختار سازمان را بسازید.
            </p>
            <Link
              href="/setup"
              className="mt-8 inline-block w-full rounded-xl bg-accent px-5 py-3 shadow-[0_8px_24px_-8px_rgb(56_189_248/0.6)] text-sm font-bold text-slate-950 transition-colors hover:bg-accent-strong sm:w-auto"
            >
              شروع راه‌اندازی
            </Link>
          </>
        ) : (
          <>
            <p className="mt-4 text-sm leading-7 text-slate-400">
              راه‌اندازی این سامانه هنوز به پایان نرسیده است. با حساب توسعه‌دهنده وارد شوید و ادامه دهید.
            </p>
            <Link
              href="/login?next=%2Fsetup"
              className="mt-8 inline-block w-full rounded-xl bg-accent px-5 py-3 shadow-[0_8px_24px_-8px_rgb(56_189_248/0.6)] text-sm font-bold text-slate-950 transition-colors hover:bg-accent-strong sm:w-auto"
            >
              ادامهٔ راه‌اندازی
            </Link>
          </>
        )}

        <p className="mt-10 text-xs text-slate-500">وی‌آی · سامانه کنترل مستندات</p>
      </div>
    </main>
  );
}
