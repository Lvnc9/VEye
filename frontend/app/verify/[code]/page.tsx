"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { formatJalali } from "@/lib/jalali";
import { VERIFY_STYLES, fetchVerification, type VerifyOutcome } from "@/lib/verify";
import { Code } from "@/components/Code";

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
    <main className="mx-auto flex min-h-screen max-w-xl flex-col gap-4 px-4 py-10">
      <header className="text-center">
        <h1 className="text-xl font-bold text-slate-900">استعلام اعتبار مستند</h1>
        <p className="mt-1 text-sm text-slate-500">سامانه کنترل مستندات</p>
      </header>

      {outcome === null && (
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-6 text-center text-sm text-slate-600">
          در حال بررسی...
        </div>
      )}

      {outcome?.kind === "not_found" && (
        <div role="alert" className="rounded-lg border border-slate-300 bg-white px-4 py-6 text-center">
          <p className="text-lg font-semibold text-slate-800">مستندی یافت نشد</p>
          <p className="mt-2 text-sm text-slate-600">{outcome.message}</p>
          <p className="mt-3 text-xs text-slate-400">
            کد واردشده: <Code>{code}</Code>
          </p>
        </div>
      )}

      {outcome?.kind === "error" && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-4 text-center text-sm text-red-700">
          {outcome.message}
        </div>
      )}

      {outcome?.kind === "ok" && (
        <section className={`space-y-4 rounded-lg border p-5 ${VERIFY_STYLES[outcome.data.state].panel}`}>
          <div className="flex items-center gap-3">
            <span
              aria-hidden
              className={`flex h-12 w-12 items-center justify-center rounded-full text-2xl font-bold ${VERIFY_STYLES[outcome.data.state].badge}`}
            >
              {VERIFY_STYLES[outcome.data.state].icon}
            </span>
            <div>
              <p className="text-2xl font-bold text-slate-900">{outcome.data.state_label}</p>
              <p className="text-sm text-slate-700">{outcome.data.message}</p>
            </div>
          </div>

          <dl className="grid grid-cols-2 gap-3 rounded bg-white/70 p-3 text-sm">
            {outcome.data.title && (
              <div className="col-span-2">
                <dt className="text-xs text-slate-500">عنوان</dt>
                <dd className="font-medium text-slate-900">{outcome.data.title}</dd>
              </div>
            )}
            <div>
              <dt className="text-xs text-slate-500">کد مستند</dt>
              <dd>
                <Code>{outcome.data.full_code}</Code>
              </dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">شماره بازنگری</dt>
              <dd>
                <Code>{outcome.data.revision_display}</Code>
              </dd>
            </div>
            {outcome.data.group_label && (
              <div>
                <dt className="text-xs text-slate-500">گروه</dt>
                <dd className="text-slate-900">{outcome.data.group_label}</dd>
              </div>
            )}
          </dl>

          {outcome.data.current_revision && (
            <p className="rounded border border-green-200 bg-white px-3 py-2 text-sm">
              آخرین بازنگری معتبر این مستند:{" "}
              <Link href={`/verify/${outcome.data.current_revision.full_code}`} className="font-semibold text-blue-700 underline">
                <Code>{outcome.data.current_revision.full_code}</Code>
              </Link>
            </p>
          )}

          {outcome.data.signers && outcome.data.signers.length > 0 && (
            <div className="overflow-x-auto rounded bg-white/70">
              <table className="w-full text-right text-sm">
                <thead className="text-xs text-slate-500">
                  <tr>
                    <th className="px-3 py-2 font-medium">مسئولیت</th>
                    <th className="px-3 py-2 font-medium">نام</th>
                    <th className="px-3 py-2 font-medium">سمت</th>
                    <th className="px-3 py-2 font-medium">تاریخ</th>
                  </tr>
                </thead>
                <tbody>
                  {outcome.data.signers.map((signer) => (
                    <tr key={signer.role_label} className="border-t border-slate-200">
                      <td className="px-3 py-2">{signer.role_label}</td>
                      <td className="px-3 py-2 font-medium">{signer.name}</td>
                      <td className="px-3 py-2">{signer.position}</td>
                      <td className="px-3 py-2">{formatJalali(signer.signed_date)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
