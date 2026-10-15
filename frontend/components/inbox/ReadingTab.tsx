"use client";

import { useState } from "react";
import Link from "next/link";
import { BookOpenCheck, Check, FileText } from "lucide-react";
import { ApiError } from "@/lib/api-client";
import { acknowledge, type PendingRead } from "@/lib/distribution";
import { formatJalali } from "@/lib/jalali";
import { usePagedQuery } from "@/lib/use-paged-query";
import { Code } from "@/components/Code";
import { Pager } from "@/components/Pager";
import { ErrorBanner } from "@/components/StatusBanner";
import { Button, buttonClass } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { SkeletonLines } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";

const PAGE_SIZE = 25;

/** «برای مطالعه» (Phase 21): the approved documents I have been asked to read. Open one, read it, and
 *  record «مطالعه کردم» — here or in the document itself. A superseded revision drops out on its own. */
export function ReadingTab({ onChanged }: { onChanged: () => void }) {
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [reload, setReload] = useState(0);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pending = usePagedQuery<PendingRead>("/distribution/pending/", { page, page_size: PAGE_SIZE }, reload);
  const totalPages = Math.max(1, Math.ceil(pending.count / PAGE_SIZE));

  async function done(row: PendingRead) {
    setBusyId(row.document.id);
    setError(null);
    try {
      await acknowledge(row.document.id);
      toast({ tone: "success", title: `مطالعهٔ ${row.document.full_code} ثبت شد.` });
      setReload((n) => n + 1);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ثبت مطالعه ممکن نشد.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card aria-label="مستندات برای مطالعه">
      <CardHeader
        title="برای مطالعه"
        icon={<BookOpenCheck />}
        description="مستندات تصویب‌شده‌ای که به شما ابلاغ شده است. پس از مطالعه، «مطالعه کردم» را بزنید."
      />
      {error && <ErrorBanner message={error} />}
      {pending.loading && pending.rows.length === 0 ? (
        <SkeletonLines rows={3} />
      ) : pending.error ? (
        <ErrorBanner message={pending.error} />
      ) : pending.rows.length === 0 ? (
        <EmptyState compact icon={<BookOpenCheck />} message="مستندی برای مطالعه ندارید." />
      ) : (
        <ul className="-mx-2 divide-y divide-border">
          {pending.rows.map((row) => (
            <li key={row.document.id} className="flex flex-wrap items-center gap-3 rounded-xl px-2 py-3 text-sm transition-colors hover:bg-accent">
              <div className="min-w-[12rem] flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <Code>{row.document.full_code}</Code>
                  <span className="text-xs text-muted-foreground">{row.document.group_label}</span>
                </div>
                <p className="mt-1 font-bold text-foreground">{row.document.title}</p>
                <p className="text-xs text-muted-foreground">ابلاغ: {formatJalali(row.asked_at)}</p>
              </div>
              <div className="flex items-center gap-2">
                <Link href={`/documents/${row.document.id}/edit`} className={buttonClass({ variant: "secondary", size: "sm" })}>
                  <FileText />
                  مشاهده
                </Link>
                <Button
                  size="sm"
                  variant="primary"
                  icon={<Check />}
                  loading={busyId === row.document.id}
                  onClick={() => void done(row)}
                >
                  مطالعه کردم
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {totalPages > 1 && <Pager page={page} totalPages={totalPages} onChange={setPage} />}
    </Card>
  );
}
