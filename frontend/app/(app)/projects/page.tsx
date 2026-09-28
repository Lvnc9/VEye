"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api-client";
import { DebouncedInput } from "@/components/history/DebouncedInput";
import { Pager } from "@/components/Pager";
import { ProjectCard } from "@/components/projects/ProjectCard";
import { ErrorBanner } from "@/components/StatusBanner";
import { FilePenLine, FolderKanban, Plus, RotateCcw } from "lucide-react";
import { Button, buttonClass } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { selectClass } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { cx } from "@/components/ui/cx";
import { PROJECT_STATUS_LABELS, parseDraftPayload, type Project, type ProjectStatus } from "@/lib/projects";
import { usePagedQuery } from "@/lib/use-paged-query";

const PAGE_SIZE = 20;
const select = cx(selectClass, "min-w-[8rem] flex-1 sm:flex-none");
const toggle =
  "flex h-10 items-center gap-2 rounded-lg px-3 text-sm text-slate-700 ring-1 ring-inset ring-slate-200 transition-colors hover:bg-slate-50 has-[:checked]:bg-brand-50 has-[:checked]:text-brand-800 has-[:checked]:ring-brand-300";

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
      <PageHeader
        title="پروژه‌ها"
        subtitle="پروژه‌های بخش‌های قابل‌مشاهده برای شما"
        actions={
          <Link href="/projects/new" className={buttonClass({ variant: "primary" })}>
            <Plus />
            پروژهٔ جدید
          </Link>
        }
      />

      <DraftProjectCard />

      <Card as="section" className="flex flex-wrap items-center gap-2 p-3 sm:gap-3 sm:p-4">
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
        <label className={toggle}>
          <input type="checkbox" className="size-4 rounded" checked={filters.mine} onChange={(e) => update({ mine: e.target.checked })} />
          فقط پروژه‌های من
        </label>
        <label className={toggle}>
          <input type="checkbox" className="size-4 rounded" checked={filters.overdue} onChange={(e) => update({ overdue: e.target.checked })} />
          دارای ریزهدف دیرکرد
        </label>
        <label className={toggle}>
          <input type="checkbox" className="size-4 rounded" checked={filters.archived} onChange={(e) => update({ archived: e.target.checked })} />
          بایگانی‌شده‌ها
        </label>
        {(filters.q || filters.status || filters.mine || filters.overdue || filters.archived) && (
          <Button
            variant="ghost"
            size="sm"
            icon={<RotateCcw />}
            className="animate-fade-in"
            onClick={() => {
              setFilters(EMPTY_FILTERS);
              setPage(1);
              setResetKey((k) => k + 1);
            }}
          >
            پاک کردن فیلترها
          </Button>
        )}
      </Card>

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" role="status" aria-label="در حال بارگذاری">
          {[0, 1, 2].map((i) => (
            <div key={i} className="space-y-4 rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-2 w-full" />
              <Skeleton className="h-6 w-1/3" />
            </div>
          ))}
        </div>
      ) : error ? (
        <ErrorBanner message={error} />
      ) : rows.length === 0 ? (
        <EmptyState icon={<FolderKanban />} message="پروژه‌ای یافت نشد." />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {rows.map((project, i) => (
            <div key={project.id} className="veye-stagger" style={{ "--i": Math.min(i, 8) } as React.CSSProperties}>
              <ProjectCard project={project} />
            </div>
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
      className="flex items-center gap-3 rounded-2xl border border-dashed border-amber-300 bg-amber-50/80 px-4 py-3 text-sm text-amber-900 transition-colors animate-fade-in hover:bg-amber-100"
    >
      <FilePenLine className="size-4 text-amber-600" />
      پیش‌نویس پروژه — برای ادامه کلیک کنید
    </Link>
  );
}
