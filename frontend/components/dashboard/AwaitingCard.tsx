"use client";

import Link from "next/link";
import { ChevronLeft, CircleCheck, ClipboardList } from "lucide-react";
import { Code } from "@/components/Code";
import { StatusBadge } from "@/components/StatusBadge";
import { ErrorBanner } from "@/components/StatusBanner";
import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { SkeletonLines } from "@/components/ui/Skeleton";
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
    <Card aria-label="منتظر اقدام شما">
      <CardHeader
        title="منتظر اقدام شما"
        icon={<ClipboardList />}
        actions={
          data &&
          data.count > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {data.by_step.submit > 0 && <Badge tone="neutral">ارسال: {data.by_step.submit}</Badge>}
              {data.by_step.confirm > 0 && <Badge tone="warning">تایید: {data.by_step.confirm}</Badge>}
              {data.by_step.approve > 0 && <Badge tone="brand">تصویب: {data.by_step.approve}</Badge>}
            </div>
          )
        }
      />

      {loading && !data && <SkeletonLines rows={3} />}
      {error && <ErrorBanner message={error} />}
      {data && data.count === 0 && (
        <EmptyState compact icon={<CircleCheck />} message="مستندی منتظر اقدام شما نیست." />
      )}

      {data && data.items.length > 0 && (
        <ul className="-mx-2 divide-y divide-slate-100">
          {data.items.map((item) => (
            <li key={item.id}>
              <Link
                href={`/documents/${item.id}/edit`}
                className="group flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-xl px-2 py-3 text-sm transition-colors hover:bg-slate-50"
              >
                <Code>{item.full_code}</Code>
                <span className="min-w-[10rem] flex-1 truncate text-slate-900">{item.title}</span>
                <StatusBadge status={item.status} label={item.status_label} />
                <span className="rounded-full bg-slate-900 px-2.5 py-0.5 text-xs text-white">{item.step_label}</span>
                <span className="ms-auto flex items-center gap-2">
                  <span className="text-xs text-slate-500" title="از این تاریخ منتظر است">
                    {formatJalali(item.waiting_since)}
                  </span>
                  <ChevronLeft className="size-4 text-slate-300 transition-transform duration-200 group-hover:-translate-x-0.5 group-hover:text-slate-500" />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {data && data.count > data.items.length && (
        <p className="mt-3 text-xs text-slate-500">
          {data.count - data.items.length} مورد دیگر — در{" "}
          <Link href="/documents" className="text-brand-700 underline-offset-4 hover:underline">
            فهرست مستندات
          </Link>{" "}
          بر اساس وضعیت فیلتر کنید.
        </p>
      )}
    </Card>
  );
}
