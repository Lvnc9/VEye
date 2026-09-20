"use client";

import Link from "next/link";
import { Code } from "@/components/Code";
import { StatusBadge } from "@/components/StatusBadge";
import { formatJalali } from "@/lib/jalali";
import { useApiQuery } from "@/lib/use-api-query";
import type { AwaitingResponse } from "@/lib/types";

/**
 * «منتظر اقدام شما» — documents waiting for the signed-in user's step. It is the
 * closest thing to V_1.0's dead کارتابل button. The server decides what is "yours"
 * with the same rule as the register's buttons, so the two never disagree; each
 * link opens the document, whose header carries the sign-off buttons.
 */
export function AwaitingCard() {
  const { data, error, loading } = useApiQuery<AwaitingResponse>("/dashboard/awaiting/");

  return (
    <section aria-label="منتظر اقدام شما" className="rounded-lg border border-slate-200 bg-white p-6">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold text-slate-900">منتظر اقدام شما</h2>
        {data && data.count > 0 && (
          <p className="text-sm text-slate-500">
            {data.by_step.submit > 0 && <span className="ms-3">ارسال: {data.by_step.submit}</span>}
            {data.by_step.confirm > 0 && <span className="ms-3">تایید: {data.by_step.confirm}</span>}
            {data.by_step.approve > 0 && <span className="ms-3">تصویب: {data.by_step.approve}</span>}
          </p>
        )}
      </div>

      {loading && <p className="text-sm text-slate-500">در حال بارگذاری...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}
      {data && data.count === 0 && <p className="text-sm text-slate-500">مستندی منتظر اقدام شما نیست.</p>}

      {data && data.items.length > 0 && (
        <ul className="divide-y divide-slate-100">
          {data.items.map((item) => (
            <li key={item.id} className="flex flex-wrap items-center gap-3 py-2.5 text-sm">
              <Code>{item.full_code}</Code>
              <Link href={`/documents/${item.id}/edit`} className="min-w-[10rem] flex-1 font-medium text-slate-900 hover:underline">
                {item.title}
              </Link>
              <StatusBadge status={item.status} label={item.status_label} />
              <span className="rounded bg-slate-900 px-2.5 py-1 text-xs font-medium text-white">{item.step_label}</span>
              <span className="text-xs text-slate-400" title="از این تاریخ منتظر است">
                {formatJalali(item.waiting_since)}
              </span>
            </li>
          ))}
        </ul>
      )}
      {data && data.count > data.items.length && (
        <p className="mt-3 text-xs text-slate-500">
          {data.count - data.items.length} مورد دیگر — در <Link href="/documents" className="underline">فهرست مستندات</Link> بر اساس وضعیت
          فیلتر کنید.
        </p>
      )}
    </section>
  );
}
