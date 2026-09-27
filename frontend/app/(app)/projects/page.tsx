"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api-client";
import { DebouncedInput } from "@/components/history/DebouncedInput";
import { Pager } from "@/components/Pager";
import { ProjectCard } from "@/components/projects/ProjectCard";
import { EmptyBanner, ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
import { PROJECT_STATUS_LABELS, parseDraftPayload, type Project, type ProjectStatus } from "@/lib/projects";
import { usePagedQuery } from "@/lib/use-paged-query";

const PAGE_SIZE = 20;
const select = "rounded border border-slate-300 bg-white px-3 py-2 text-sm";

interface Filters {
  q: string;
  status: ProjectStatus | "";
  mine: boolean;
  overdue: boolean;
  archived: boolean;
}

const EMPTY_FILTERS: Filters = { q: "", status: "", mine: false, overdue: false, archived: false };

/** «پروژه‌ها» (docs/11 §3.5): every project the viewer may read, in their visible بخش‌ها. */
export default function ProjectsPage() {
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [resetKey, setResetKey] = useState(0);

  function update(patch: Partial<Filters>) {
    setFilters({ ...filters, ...patch });
    setPage(1);
  }

  const { rows, count, error, loading } = usePagedQuery<Project>("/projects/", {
    page,
    page_size: PAGE_SIZE,
    q: filters.q,
    status: filters.status,
    mine: filters.mine ? "1" : "",
    overdue: filters.overdue ? "1" : "",
    archived: filters.archived ? "1" : "",
  });
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">پروژه‌ها</h1>
          <p className="mt-1 text-sm text-slate-500">پروژه‌های بخش‌های قابل‌مشاهده برای شما</p>
        </div>
        <Link href="/projects/new" className="rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700">
          پروژهٔ جدید
        </Link>
      </header>

      <DraftProjectCard />

      <section className="flex flex-wrap items-center gap-3">
        <DebouncedInput
          key={resetKey}
          value={filters.q}
          onCommit={(q) => update({ q })}
          placeholder="جست و جوی نام پروژه"
          ariaLabel="جست و جوی پروژه"
        />
        <select
          aria-label="وضعیت"
          value={filters.status}
          onChange={(e) => update({ status: e.target.value as ProjectStatus | "" })}
          className={select}
        >
          <option value="">همهٔ وضعیت‌ها</option>
          {(Object.keys(PROJECT_STATUS_LABELS) as ProjectStatus[]).map((value) => (
            <option key={value} value={value}>
              {PROJECT_STATUS_LABELS[value]}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={filters.mine} onChange={(e) => update({ mine: e.target.checked })} />
          فقط پروژه‌های من
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={filters.overdue} onChange={(e) => update({ overdue: e.target.checked })} />
          دارای ریزهدف دیرکرد
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={filters.archived} onChange={(e) => update({ archived: e.target.checked })} />
          بایگانی‌شده‌ها
        </label>
        {(filters.q || filters.status || filters.mine || filters.overdue || filters.archived) && (
          <button
            type="button"
            onClick={() => {
              setFilters(EMPTY_FILTERS);
              setPage(1);
              setResetKey((k) => k + 1);
            }}
            className="text-sm text-slate-500 underline hover:text-slate-800"
          >
            پاک کردن فیلترها
          </button>
        )}
      </section>

      {loading ? (
        <LoadingBanner />
      ) : error ? (
        <ErrorBanner message={error} />
      ) : rows.length === 0 ? (
        <EmptyBanner message="پروژه‌ای یافت نشد." />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      )}

      <Pager page={page} totalPages={totalPages} onChange={setPage} />
    </div>
  );
}

/** «پیش‌نویس پروژه»: shown only once the draft has been confirmed as a well-shaped, current-version
 *  one — otherwise the link would land on /projects/new with nothing to continue. Errors are swallowed:
 *  a failed check just means the card doesn't appear, never a page-blocking error. */
function DraftProjectCard() {
  const [hasDraft, setHasDraft] = useState(false);

  useEffect(() => {
    let cancelled = false;
    apiGet<{ payload: unknown; updated_at: string | null }>("/projects/draft/")
      .then((res) => !cancelled && setHasDraft(Boolean(parseDraftPayload(res.payload))))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (!hasDraft) return null;
  return (
    <Link
      href="/projects/new"
      className="block rounded-lg border border-dashed border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 hover:bg-amber-100"
    >
      پیش‌نویس پروژه — برای ادامه کلیک کنید
    </Link>
  );
}
