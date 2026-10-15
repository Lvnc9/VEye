"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, FileCheck2, Network, ShieldCheck } from "lucide-react";
import { apiGet, apiGetIfSignedIn } from "@/lib/api-client";
import type { SetupStatus, User } from "@/lib/types";
import { AnimatedBackground } from "@/components/ui/AnimatedBackground";
import { BrandMark } from "@/components/ui/BrandMark";
import { buttonClass } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";

const HIGHLIGHTS = [
  { icon: FileCheck2, text: "تدوین، تایید و تصویب مستندات با امضا" },
  { icon: Network, text: "ساختار سازمان، پروژه‌ها و کارتابل" },
  { icon: ShieldCheck, text: "اعتبارسنجی هر نسخهٔ چاپی با QR" },
];

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
      <main className="relative isolate flex min-h-dvh items-center justify-center">
        <AnimatedBackground beams={false} />
        <p className="flex items-center gap-2 text-sm text-slate-400">
          <Spinner className="text-glow" />
          در حال بارگذاری...
        </p>
      </main>
    );
  }

  const cta =
    status === null
      ? { href: "/login", label: "ورود به سامانه", note: "دریافت وضعیت سامانه ممکن نشد. اتصال خود را بررسی کنید.", primary: false }
      : !status.developer_exists
        ? {
            href: "/setup",
            label: "شروع راه‌اندازی",
            note: "این سامانه هنوز راه‌اندازی نشده است. با چند مرحلهٔ ساده، حساب توسعه‌دهنده و ساختار سازمان را بسازید.",
            primary: true,
          }
        : {
            href: "/login?next=%2Fsetup",
            label: "ادامهٔ راه‌اندازی",
            note: "راه‌اندازی این سامانه هنوز به پایان نرسیده است. با حساب توسعه‌دهنده وارد شوید و ادامه دهید.",
            primary: true,
          };

  return (
    <main className="relative isolate flex min-h-dvh flex-col items-center justify-center px-5 py-12 text-slate-100">
      <AnimatedBackground />
      <div className="w-full max-w-lg text-center">
        <div className="veye-rise mb-8 flex items-center justify-center gap-3" style={{ "--i": 0 } as React.CSSProperties}>
          <BrandMark size="lg" />
          <span className="text-xl font-extrabold">وی‌آی</span>
        </div>

        <span
          className="veye-rise mb-5 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-slate-300 backdrop-blur"
          style={{ "--i": 1 } as React.CSSProperties}
        >
          <span className="size-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgb(52_211_153/0.8)]" />
          سامانه کنترل مستندات
        </span>

        <h1 className="veye-rise text-3xl leading-[1.45] font-black sm:text-4xl sm:leading-[1.45]" style={{ "--i": 2 } as React.CSSProperties}>
          سازمان شما،
          <br />
          <span className="bg-gradient-to-l from-sky-300 via-glow to-indigo-300 bg-clip-text text-transparent">
            منظم، کنترل‌شده و قابل‌پیگیری.
          </span>
        </h1>

        <div className="veye-rise veye-glass mt-8 rounded-3xl p-6 text-start sm:p-7" style={{ "--i": 3 } as React.CSSProperties}>
          <p className="text-sm leading-7 text-slate-300">{cta.note}</p>
          <Link
            href={cta.href}
            className={buttonClass({ variant: cta.primary ? "glow" : "navy-ghost", size: "lg", className: "group mt-5 w-full" })}
          >
            {cta.label}
            <ArrowLeft className="size-4 transition-transform duration-200 group-hover:-translate-x-1" />
          </Link>
          <ul className="mt-6 space-y-2.5 border-t border-white/[0.06] pt-5">
            {HIGHLIGHTS.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-center gap-3 text-sm text-slate-400">
                <span className="flex size-7 items-center justify-center rounded-lg bg-glow/10 text-glow ring-1 ring-inset ring-glow/20">
                  <Icon className="size-3.5" />
                </span>
                {text}
              </li>
            ))}
          </ul>
        </div>

        <p className="veye-rise mt-10 text-xs text-slate-500" style={{ "--i": 4 } as React.CSSProperties}>
          وی‌آی · سامانه کنترل مستندات
        </p>
      </div>
    </main>
  );
}
