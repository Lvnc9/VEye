"use client";

import { useState } from "react";
import { Code } from "@/components/Code";
import { Pager } from "@/components/Pager";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyBanner, ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
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
const select = "rounded border border-slate-300 bg-white px-3 py-2 text-sm";

function Signer({ signoff }: { signoff: SignOffSummary | null }) {
  if (!signoff?.name) return <span className="text-slate-300">—</span>;
  return (
    <span title={signoff.position}>
      {signoff.name}
      {signoff.signed_date && <span className="block text-xs text-slate-400">{formatJalali(signoff.signed_date)}</span>}
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
      <section className="flex flex-wrap items-center gap-3">
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
          <button
            type="button"
            onClick={() => {
              onFilters(EMPTY_REVISION_FILTERS);
              setResetKey((n) => n + 1);
              setPage(1);
            }}
            className="text-sm text-slate-600 underline"
          >
            پاک کردن فیلترها
          </button>
        )}
        <span className="ms-auto text-sm text-slate-500">{count} بازنگری</span>
      </section>

      {filters.family && (
        <p className="rounded border border-blue-200 bg-blue-50 px-4 py-2 text-sm text-blue-800">
          همهٔ بازنگری‌های مستند <Code>{filters.family}</Code>
          <button type="button" onClick={() => update({ family: "" })} className="ms-3 underline">
            نمایش همهٔ مستندات
          </button>
        </p>
      )}

      {error && <ErrorBanner message={error} />}
      {loading && rows.length === 0 && <LoadingBanner />}
      {!error && !loading && rows.length === 0 && (
        <EmptyBanner message={hasActiveFilters(filters) ? "بازنگری‌ای با این مشخصات یافت نشد." : "هنوز مستندی ثبت نشده است."} />
      )}

      {rows.length > 0 && (
        <div className={`overflow-x-auto rounded-lg border border-slate-200 bg-white ${loading ? "opacity-60" : ""}`}>
          <table className="w-full min-w-[980px] text-right text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                {["کد", "بازنگری", "عنوان", "گروه", "وضعیت", "تدوین", "تائید", "تصویب", "PDF"].map((column) => (
                  <th key={column} className="whitespace-nowrap px-3 py-3 font-medium">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-3 py-3">
                    <button
                      type="button"
                      title="نمایش همهٔ بازنگری‌های این مستند"
                      onClick={() => update({ family: row.code })}
                      className="underline decoration-dotted"
                    >
                      <Code>{row.code}</Code>
                    </button>
                  </td>
                  <td className="px-3 py-3">
                    <Code>{row.revision_display}</Code>
                  </td>
                  <td className="max-w-[260px] truncate px-3 py-3 font-medium text-slate-900" title={row.title}>
                    {row.title}
                  </td>
                  <td className="whitespace-nowrap px-3 py-3">{row.group_label}</td>
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
                    {row.pdf_status === "ready" ? (
                      <a
                        href={pdfDownloadUrl(row.id)}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded border border-slate-300 bg-white px-2 py-1 text-xs hover:bg-slate-50"
                      >
                        باز کردن
                      </a>
                    ) : (
                      <span className="text-slate-300">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Pager page={Math.min(page, totalPages)} totalPages={totalPages} onChange={setPage} />
    </div>
  );
}
