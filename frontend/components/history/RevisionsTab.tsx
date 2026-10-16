"use client";

import Link from "next/link";
import { useState } from "react";
import { Code } from "@/components/Code";
import { Pager } from "@/components/Pager";
import { StatusBadge } from "@/components/StatusBadge";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
import { ExternalLink, FileText, GitCompareArrows, RotateCcw, SearchX, X } from "lucide-react";
import { Alert } from "@/components/ui/Alert";
import { Button, buttonClass } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { selectClass } from "@/components/ui/Field";
import { cx } from "@/components/ui/cx";

import { DebouncedInput } from "@/components/history/DebouncedInput";
import { EMPTY_REVISION_FILTERS, hasActiveFilters, revisionParams, type RevisionFilters } from "@/lib/history";
import { formatJalali } from "@/lib/jalali";
import { pdfDownloadUrl } from "@/lib/pdf";
import { usePagedQuery } from "@/lib/use-paged-query";
import {
  DOCUMENT_GROUP_LABELS,
  DOCUMENT_STATUS_LABELS,
  type DocumentGroup,
  type DocumentStatus,
  type RevisionRow,
  type SignOffSummary,
} from "@/lib/types";

const PAGE_SIZE = 25;
const select = cx(selectClass, "min-w-[8rem] flex-1 sm:flex-none");

function Signer({ signoff }: { signoff: SignOffSummary | null }) {
  if (!signoff?.name) return <span className="text-subtle-foreground">—</span>;
  return (
    <span title={signoff.position}>
      {signoff.name}
      {signoff.signed_date && <span className="block text-xs text-muted-foreground">{formatJalali(signoff.signed_date)}</span>}
    </span>
  );
}

/**
 * Every revision of every document (سوابق مستندات ← بازنگری‌ها). Clicking a code
 * narrows the list to that document's whole revision chain.
 */
export function RevisionsTab({
  filters,
  onFilters,
}: {
  filters: RevisionFilters;
  onFilters: (filters: RevisionFilters) => void;
}) {
  const [page, setPage] = useState(1);
  const [resetKey, setResetKey] = useState(0);
  const { rows, count, error, loading } = usePagedQuery<RevisionRow>(
    "/history/revisions/",
    revisionParams(filters, page, PAGE_SIZE),
  );
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  function update(patch: Partial<RevisionFilters>) {
    onFilters({ ...filters, ...patch });
    setPage(1);
  }

  return (
    <div className="space-y-4">
      <Card as="section" className="flex flex-wrap items-center gap-2 p-3 sm:gap-3 sm:p-4">
        <DebouncedInput
          key={resetKey}
          value={filters.search}
          onCommit={(search) => update({ search })}
          placeholder="جست و جو — عنوان یا کد مستند"
          ariaLabel="جست و جوی بازنگری‌ها"
        />
        <select
          aria-label="گروه"
          value={filters.group}
          onChange={(e) => update({ group: e.target.value as DocumentGroup | "" })}
          className={select}
        >
          <option value="">همه گروه‌ها</option>
          {(Object.keys(DOCUMENT_GROUP_LABELS) as DocumentGroup[]).map((value) => (
            <option key={value} value={value}>
              {DOCUMENT_GROUP_LABELS[value]}
            </option>
          ))}
        </select>
        <select
          aria-label="وضعیت"
          value={filters.status}
          onChange={(e) => update({ status: e.target.value as DocumentStatus | "" })}
          className={select}
        >
          <option value="">همه وضعیت‌ها</option>
          {(Object.keys(DOCUMENT_STATUS_LABELS) as DocumentStatus[]).map((value) => (
            <option key={value} value={value}>
              {DOCUMENT_STATUS_LABELS[value]}
            </option>
          ))}
        </select>
        {hasActiveFilters(filters) && (
          <Button
            variant="ghost"
            size="sm"
            icon={<RotateCcw />}
            className="animate-fade-in"
            onClick={() => {
              onFilters(EMPTY_REVISION_FILTERS);
              setResetKey((n) => n + 1);
              setPage(1);
            }}
          >
            پاک کردن فیلترها
          </Button>
        )}
        <span className="ms-auto rounded-full bg-muted px-2.5 py-0.5 text-xs text-soft-foreground tabular-nums">
          {count} بازنگری
        </span>
      </Card>

      {filters.family && (
        <Alert
          tone="info"
          actions={
            <Button size="xs" variant="ghost" icon={<X />} onClick={() => update({ family: "" })}>
              نمایش همهٔ مستندات
            </Button>
          }
        >
          همهٔ بازنگری‌های مستند <Code>{filters.family}</Code>
        </Alert>
      )}

      {error && <ErrorBanner message={error} />}
      {loading && rows.length === 0 && <LoadingBanner />}
      {!error && !loading && rows.length === 0 && (
        <EmptyState
          icon={hasActiveFilters(filters) ? <SearchX /> : <FileText />}
          message={hasActiveFilters(filters) ? "بازنگری‌ای با این مشخصات یافت نشد." : "هنوز مستندی ثبت نشده است."}
        />
      )}

      {rows.length > 0 && (
        <Card as="div" flush className={cx("@container overflow-hidden transition-opacity duration-200", loading && "opacity-60")}>
        <div className="hidden overflow-x-auto @5xl:block">
          <table className="w-full min-w-[960px] text-right text-sm">
            <thead className="bg-muted/50 text-xs text-muted-foreground">
              <tr className="border-b border-border">
                {["کد", "بازنگری", "عنوان", "گروه", "وضعیت", "تدوین", "تائید", "تصویب", "PDF"].map((column) => (
                  <th key={column} className="whitespace-nowrap px-3 py-3 font-normal">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((row) => (
                <tr key={row.id} className="transition-colors duration-150 hover:bg-accent/60">
                  <td className="px-3 py-3">
                    <button
                      type="button"
                      title="نمایش همهٔ بازنگری‌های این مستند"
                      onClick={() => update({ family: row.code })}
                      className="rounded-md transition-transform hover:scale-105"
                    >
                      <Code>{row.code}</Code>
                    </button>
                  </td>
                  <td className="px-3 py-3">
                    <Code>{row.revision_display}</Code>
                  </td>
                  <td className="max-w-[260px] truncate px-3 py-3 font-bold text-foreground" title={row.title}>
                    {row.title}
                  </td>
                  <td className="whitespace-nowrap px-3 py-3 text-soft-foreground">{row.group_label}</td>
                  <td className="px-3 py-3">
                    <StatusBadge status={row.status} label={row.status_label} />
                  </td>
                  <td className="px-3 py-3">
                    <Signer signoff={row.signoffs.creater} />
                  </td>
                  <td className="px-3 py-3">
                    <Signer signoff={row.signoffs.confirmer} />
                  </td>
                  <td className="px-3 py-3">
                    <Signer signoff={row.signoffs.approver} />
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex flex-wrap items-center gap-1.5">
                      {row.pdf_status === "ready" ? (
                        <a
                          href={pdfDownloadUrl(row.id)}
                          target="_blank"
                          rel="noreferrer"
                          className={buttonClass({ size: "xs" })}
                        >
                          <ExternalLink />
                          باز کردن
                        </a>
                      ) : (
                        <span className="text-subtle-foreground">—</span>
                      )}
                      {row.revision > 1 && (
                        <Link href={`/documents/${row.id}/compare`} className={buttonClass({ size: "xs", variant: "ghost" })}>
                          <GitCompareArrows />
                          مقایسه با قبلی
                        </Link>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {/* Below `md`: a card per revision instead of the wide table. */}
        <ul className="divide-y divide-border @2xl:grid @2xl:grid-cols-2 @2xl:gap-px @2xl:divide-y-0 @2xl:bg-border @5xl:hidden">
          {rows.map((row) => (
            <li key={row.id} className="space-y-2.5 bg-card p-4">
              <div className="flex flex-wrap items-center gap-1.5">
                <button
                  type="button"
                  title="نمایش همهٔ بازنگری‌های این مستند"
                  onClick={() => update({ family: row.code })}
                  className="rounded-md"
                >
                  <Code>{row.code}</Code>
                </button>
                <Code>{row.revision_display}</Code>
                <StatusBadge status={row.status} label={row.status_label} />
              </div>
              <p className="font-bold leading-7 text-foreground">{row.title}</p>
              <p className="text-xs text-muted-foreground">{row.group_label}</p>
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-soft-foreground">
                <span>
                  {[row.signoffs.creater, row.signoffs.confirmer, row.signoffs.approver]
                    .map((signoff) => signoff?.name)
                    .filter(Boolean)
                    .join(" · ") || "—"}
                </span>
                <span className="flex flex-wrap gap-1.5">
                  {row.revision > 1 && (
                    <Link href={`/documents/${row.id}/compare`} className={buttonClass({ size: "xs", variant: "ghost" })}>
                      <GitCompareArrows />
                      مقایسه با قبلی
                    </Link>
                  )}
                  {row.pdf_status === "ready" && (
                    <a href={pdfDownloadUrl(row.id)} target="_blank" rel="noreferrer" className={buttonClass({ size: "xs" })}>
                      <ExternalLink />
                      باز کردن PDF
                    </a>
                  )}
                </span>
              </div>
            </li>
          ))}
        </ul>
        </Card>
      )}

      <Pager page={Math.min(page, totalPages)} totalPages={totalPages} onChange={setPage} />
    </div>
  );
}
