"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { DebouncedInput } from "@/components/history/DebouncedInput";
import { NcFormDialog } from "@/components/quality/NcFormDialog";
import { NcListItem } from "@/components/quality/NcListItem";
import { Pager } from "@/components/Pager";
import { ErrorBanner } from "@/components/StatusBanner";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { selectClass } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { cx } from "@/components/ui/cx";
import { Plus, RotateCcw, ShieldAlert } from "lucide-react";
import {
  EMPTY_NC_FILTERS,
  NC_SEVERITY_LABELS,
  NC_SOURCE_LABELS,
  NC_STATUS_LABELS,
  hasActiveFilters,
  ncQueryParams,
  type NcFilters,
  type NcMine,
  type NcSeverity,
  type NcSource,
  type NcStatus,
  type NonConformance,
} from "@/lib/quality";
import { usePagedQuery } from "@/lib/use-paged-query";

const PAGE_SIZE = 20;
const select = cx(selectClass, "min-w-[8rem] flex-1 sm:flex-none");
const toggle =
  "flex h-10 items-center gap-2 rounded-lg px-3 text-sm text-slate-700 ring-1 ring-inset ring-slate-200 transition-colors hover:bg-slate-50 has-[:checked]:bg-brand-50 has-[:checked]:text-brand-800 has-[:checked]:ring-brand-300";

const MINE_OPTIONS: { value: NcMine; label: string }[] = [
  { value: "", label: "همهٔ مواردی که می‌بینم" },
  { value: "reported", label: "ثبت‌شده توسط من" },
  { value: "assigned", label: "اقدام‌های من" },
  { value: "manage", label: "در حوزهٔ مسئولیت من" },
];

/** «عدم‌انطباق‌ها» (Phase 18): the problems the viewer may read — they reported it, lead its unit or one
 *  above it, hold an action on it, or manage quality. Anyone signed in may report one. */
export default function QualityPage() {
  const router = useRouter();
  const [filters, setFilters] = useState<NcFilters>(EMPTY_NC_FILTERS);
  const [page, setPage] = useState(1);
  const [resetKey, setResetKey] = useState(0);
  const [reporting, setReporting] = useState(false);

  function update(patch: Partial<NcFilters>) {
    setFilters({ ...filters, ...patch });
    setPage(1);
  }

  const { rows, count, error, loading } = usePagedQuery<NonConformance>(
    "/quality/nonconformances/",
    ncQueryParams(filters, page, PAGE_SIZE),
  );
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <PageHeader
        title="عدم‌انطباق‌ها"
        subtitle="مشکلاتی که ثبت شده‌اند، اقدام اصلاحی آن‌ها و نتیجه"
        actions={
          <Button variant="primary" icon={<Plus />} onClick={() => setReporting(true)}>
            ثبت عدم‌انطباق
          </Button>
        }
      />

      <Card as="section" className="flex flex-wrap items-center gap-2 p-3 sm:gap-3 sm:p-4">
        <DebouncedInput
          key={resetKey}
          value={filters.q}
          onCommit={(q) => update({ q })}
          placeholder="جست و جوی عنوان، شرح یا کد (NC-0042)"
          ariaLabel="جست و جوی عدم‌انطباق"
        />
        <select aria-label="وضعیت" value={filters.status} onChange={(e) => update({ status: e.target.value as NcStatus | "" })} className={select}>
          <option value="">همهٔ وضعیت‌ها</option>
          {(Object.keys(NC_STATUS_LABELS) as NcStatus[]).map((value) => (
            <option key={value} value={value}>
              {NC_STATUS_LABELS[value]}
            </option>
          ))}
        </select>
        <select aria-label="شدت" value={filters.severity} onChange={(e) => update({ severity: e.target.value as NcSeverity | "" })} className={select}>
          <option value="">همهٔ شدت‌ها</option>
          {(Object.keys(NC_SEVERITY_LABELS) as NcSeverity[]).map((value) => (
            <option key={value} value={value}>
              {NC_SEVERITY_LABELS[value]}
            </option>
          ))}
        </select>
        <select aria-label="منبع" value={filters.source} onChange={(e) => update({ source: e.target.value as NcSource | "" })} className={select}>
          <option value="">همهٔ منبع‌ها</option>
          {(Object.keys(NC_SOURCE_LABELS) as NcSource[]).map((value) => (
            <option key={value} value={value}>
              {NC_SOURCE_LABELS[value]}
            </option>
          ))}
        </select>
        <select aria-label="مربوط به من" value={filters.mine} onChange={(e) => update({ mine: e.target.value as NcMine })} className={select}>
          {MINE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <label className={toggle}>
          <input type="checkbox" className="size-4 rounded" checked={filters.overdue} onChange={(e) => update({ overdue: e.target.checked })} />
          دارای اقدام دیرکرد
        </label>
        {hasActiveFilters(filters) && (
          <Button
            variant="ghost"
            size="sm"
            icon={<RotateCcw />}
            className="animate-fade-in"
            onClick={() => {
              setFilters(EMPTY_NC_FILTERS);
              setPage(1);
              setResetKey((k) => k + 1);
            }}
          >
            پاک کردن فیلترها
          </Button>
        )}
      </Card>

      {loading ? (
        <Card flush role="status" aria-label="در حال بارگذاری">
          {[0, 1, 2].map((i) => (
            <div key={i} className="space-y-2.5 border-b border-slate-100 px-5 py-4 last:border-0">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-3 w-1/3" />
            </div>
          ))}
        </Card>
      ) : error ? (
        <ErrorBanner message={error} />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={<ShieldAlert />}
          message={hasActiveFilters(filters) ? "موردی با این فیلترها پیدا نشد." : "هنوز عدم‌انطباقی ثبت نشده یا شما حق دیدن آن را ندارید."}
        />
      ) : (
        <Card flush>
          <ul className="divide-y divide-slate-100">
            {rows.map((nc) => (
              <NcListItem key={nc.id} nc={nc} />
            ))}
          </ul>
        </Card>
      )}

      <Pager page={page} totalPages={totalPages} onChange={setPage} />

      {reporting && (
        <NcFormDialog
          onSaved={(saved) => {
            setReporting(false);
            router.push(`/quality/${saved.id}`);
          }}
          onClose={() => setReporting(false)}
        />
      )}
    </div>
  );
}
