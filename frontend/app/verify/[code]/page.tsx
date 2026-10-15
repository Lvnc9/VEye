"use client";

import { useEffect, useState, type ComponentType } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { FileQuestion, ShieldAlert, ShieldCheck, ShieldX, WifiOff } from "lucide-react";
import { formatJalali } from "@/lib/jalali";
import { VERIFY_STYLES, fetchVerification, type VerifyOutcome } from "@/lib/verify";
import { Code } from "@/components/Code";
import { BrandMark } from "@/components/ui/BrandMark";
import { Skeleton } from "@/components/ui/Skeleton";
import type { VerifyState } from "@/lib/types";

const SEAL: Record<VerifyState, ComponentType<{ className?: string }>> = {
  valid: ShieldCheck,
  obsolete: ShieldX,
  pending: ShieldAlert,
};

/**
 * Public landing page for a printed document's QR code: `/verify/{code}`.
 * No sign-in — the person scanning is usually not a user. The verdict is read
 * live from the server, so a superseded revision's QR says «منسوخ» and points
 * at the revision in force (V_1.0's QR served a static PDF that said معتبر forever).
 */
export default function VerifyPage() {
  const { code } = useParams<{ code: string }>();
  const [result, setResult] = useState<{ code: string; outcome: VerifyOutcome } | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchVerification(code).then((outcome) => {
      if (!cancelled) setResult({ code, outcome });
    });
    return () => {
      cancelled = true;
    };
  }, [code]);

  // Derived, not set in the effect: "the answer for this code hasn't come back".
  const outcome = result?.code === code ? result.outcome : null;

  return (
    <main className="relative min-h-screen overflow-hidden bg-canvas">
      {/* A navy band behind the card, as on the sign-in page. */}
      <div aria-hidden className="absolute inset-x-0 top-0 h-72 overflow-hidden bg-gradient-to-b from-navy to-navy-raised">
        <div className="veye-aurora absolute -top-24 left-1/2 size-96 -translate-x-1/2 rounded-full bg-glow/20 blur-3xl" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_1px_1px,rgb(148_163_184/0.14)_1px,transparent_0)] bg-[length:22px_22px] [mask-image:linear-gradient(to_bottom,black,transparent)]" />
      </div>

      <div className="relative mx-auto flex min-h-screen max-w-xl flex-col gap-5 px-4 py-8 sm:py-12">
        <header className="flex items-center justify-center gap-3 text-white veye-rise">
          <BrandMark size="sm" />
          <div>
            <h1 className="text-lg font-bold leading-7">استعلام اعتبار مستند</h1>
            <p className="text-xs text-slate-400">وی‌آی · سامانه کنترل مستندات</p>
          </div>
        </header>

        <div className="rounded-3xl border border-border bg-card shadow-overlay animate-scale-in">
          {outcome === null && (
            <div role="status" className="space-y-4 p-6">
              <div className="flex flex-col items-center gap-3">
                <Skeleton className="size-16 rounded-full" />
                <p className="text-sm text-muted-foreground">در حال بررسی...</p>
              </div>
              <Skeleton className="h-3 w-3/4" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          )}

          {outcome?.kind === "not_found" && (
            <div role="alert" className="flex flex-col items-center gap-3 px-6 py-10 text-center">
              <span className="flex size-16 items-center justify-center rounded-full bg-muted text-muted-foreground ring-8 ring-muted/60">
                <FileQuestion className="size-8" />
              </span>
              <p className="text-xl font-bold text-foreground">مستندی یافت نشد</p>
              <p className="text-sm leading-7 text-soft-foreground">{outcome.message}</p>
              <p className="text-xs text-muted-foreground">
                کد واردشده: <Code>{code}</Code>
              </p>
            </div>
          )}

          {outcome?.kind === "error" && (
            <div role="alert" className="flex flex-col items-center gap-3 px-6 py-10 text-center">
              <span className="flex size-16 items-center justify-center rounded-full bg-rose-50 text-rose-500 ring-8 ring-rose-50/60 dark:bg-rose-500/10 dark:ring-rose-500/5">
                <WifiOff className="size-8" />
              </span>
              <p className="text-sm leading-7 text-rose-700 dark:text-rose-400">{outcome.message}</p>
            </div>
          )}

          {outcome?.kind === "ok" &&
            (() => {
              const style = VERIFY_STYLES[outcome.data.state];
              const Seal = SEAL[outcome.data.state];
              return (
                <section className="overflow-hidden rounded-3xl">
                  <div aria-hidden className={`h-1.5 bg-gradient-to-l ${style.band}`} />
                  <div className="flex flex-col items-center gap-3 px-6 pt-8 pb-6 text-center">
                    <span className={`flex size-16 items-center justify-center rounded-full animate-pop ${style.badge}`}>
                      <Seal className="size-8" />
                    </span>
                    <p className={`text-2xl font-black ${style.text}`}>{outcome.data.state_label}</p>
                    <p className="max-w-sm text-sm leading-7 text-soft-foreground">{outcome.data.message}</p>
                  </div>

                  <dl className="grid grid-cols-2 gap-px border-y border-border bg-border text-sm">
                    {outcome.data.title && (
                      <div className="col-span-2 bg-card px-5 py-3">
                        <dt className="text-xs text-muted-foreground">عنوان</dt>
                        <dd className="mt-0.5 font-bold text-foreground">{outcome.data.title}</dd>
                      </div>
                    )}
                    <div className="bg-card px-5 py-3">
                      <dt className="text-xs text-muted-foreground">کد مستند</dt>
                      <dd className="mt-1">
                        <Code>{outcome.data.full_code}</Code>
                      </dd>
                    </div>
                    <div className="bg-card px-5 py-3">
                      <dt className="text-xs text-muted-foreground">شماره بازنگری</dt>
                      <dd className="mt-1">
                        <Code>{outcome.data.revision_display}</Code>
                      </dd>
                    </div>
                    {outcome.data.group_label && (
                      <div className="col-span-2 bg-card px-5 py-3">
                        <dt className="text-xs text-muted-foreground">گروه</dt>
                        <dd className="mt-0.5 text-foreground">{outcome.data.group_label}</dd>
                      </div>
                    )}
                  </dl>

                  {outcome.data.current_revision && (
                    <p className="mx-5 mt-5 rounded-xl border border-emerald-200 bg-emerald-50/70 px-4 py-3 text-sm text-emerald-900 dark:border-emerald-400/20 dark:bg-emerald-400/[0.07] dark:text-emerald-100">
                      آخرین بازنگری معتبر این مستند:{" "}
                      <Link
                        href={`/verify/${outcome.data.current_revision.full_code}`}
                        className="font-bold text-primary underline-offset-4 hover:underline"
                      >
                        <Code>{outcome.data.current_revision.full_code}</Code>
                      </Link>
                    </p>
                  )}

                  {outcome.data.signers && outcome.data.signers.length > 0 && (
                    <div className="p-5">
                      <h2 className="mb-3 text-xs font-bold text-muted-foreground">امضاکنندگان</h2>
                      {/* A list of cards on a phone, a table from `sm` up. */}
                      <ul className="space-y-2 sm:hidden">
                        {outcome.data.signers.map((signer) => (
                          <li key={signer.role_label} className="rounded-xl border border-border bg-muted/40 px-4 py-3 text-sm">
                            <div className="flex items-center justify-between gap-3">
                              <span className="text-xs text-muted-foreground">{signer.role_label}</span>
                              <span className="whitespace-nowrap text-xs text-muted-foreground">{formatJalali(signer.signed_date)}</span>
                            </div>
                            <p className="mt-1 font-bold text-foreground">{signer.name}</p>
                            <p className="text-xs text-soft-foreground">{signer.position}</p>
                          </li>
                        ))}
                      </ul>
                      <div className="hidden overflow-x-auto rounded-xl border border-border sm:block">
                        <table className="w-full text-right text-sm">
                          <thead className="bg-muted/60 text-xs text-muted-foreground">
                            <tr>
                              <th className="px-3 py-2.5 font-normal">مسئولیت</th>
                              <th className="px-3 py-2.5 font-normal">نام</th>
                              <th className="px-3 py-2.5 font-normal">سمت</th>
                              <th className="px-3 py-2.5 font-normal">تاریخ</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-border">
                            {outcome.data.signers.map((signer) => (
                              <tr key={signer.role_label}>
                                <td className="px-3 py-2.5 text-soft-foreground">{signer.role_label}</td>
                                <td className="px-3 py-2.5 font-bold text-foreground">{signer.name}</td>
                                <td className="px-3 py-2.5 text-soft-foreground">{signer.position}</td>
                                <td className="whitespace-nowrap px-3 py-2.5 text-soft-foreground">{formatJalali(signer.signed_date)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                  {!(outcome.data.signers && outcome.data.signers.length > 0) && <div className="h-5" />}
                </section>
              );
            })()}
        </div>

      </div>
    </main>
  );
}
