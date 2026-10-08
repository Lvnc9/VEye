"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Gauge, Grid3x3, Plus, RotateCcw, X } from "lucide-react";
import { DebouncedInput } from "@/components/history/DebouncedInput";
import { RiskFormDialog } from "@/components/quality/RiskFormDialog";
import { RiskHeatMap } from "@/components/quality/RiskHeatMap";
import { RiskListItem } from "@/components/quality/RiskListItem";
import { Pager } from "@/components/Pager";
import { ErrorBanner } from "@/components/StatusBanner";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { selectClass } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton, SkeletonLines } from "@/components/ui/Skeleton";
import { cx } from "@/components/ui/cx";
import { useCurrentUser } from "@/lib/current-user";
import { toPersianDigits } from "@/lib/jalali";
import {
  EMPTY_RISK_FILTERS,
  RISK_LEVEL_LABELS,
  RISK_STATUS_LABELS,
  hasActiveRiskFilters,
  riskQueryParams,
  type RiskFilters,
  type RiskItem,
  type RiskLevel,
  type RiskMatrix,
  type RiskMine,
  type RiskStatus,
} from "@/lib/quality";
import { useApiQuery } from "@/lib/use-api-query";
import { usePagedQuery } from "@/lib/use-paged-query";

const PAGE_SIZE = 20;
const select = cx(selectClass, "min-w-[8rem] flex-1 sm:flex-none");
const toggle =
  "flex h-10 items-center gap-2 rounded-lg px-3 text-sm text-slate-700 ring-1 ring-inset ring-slate-200 transition-colors hover:bg-slate-50 has-[:checked]:bg-brand-50 has-[:checked]:text-brand-800 has-[:checked]:ring-brand-300";

const MINE_OPTIONS: { value: RiskMine; label: string }[] = [
  { value: "", label: "همهٔ ریسک‌هایی که می‌بینم" },
  { value: "owner", label: "مسئول پیگیری آن‌ها هستم" },
  { value: "created", label: "ثبت‌شده توسط من" },
  { value: "manage", label: "در حوزهٔ مسئولیت من" },
];

/** «ریسک‌ها» (Phase 18): the heat map of the risks still on the register, and the register itself, worst
 *  first. A cell of the map filters the list. Recording a risk is for `manage_quality` or a مسئول (of the
 *  node or one above it), so the button is shown only to someone who holds one of those. */
export default function RisksPage() {
  const router = useRouter();
  const { user, can } = useCurrentUser();
  const [filters, setFilters] = useState<RiskFilters>(EMPTY_RISK_FILTERS);
  const [page, setPage] = useState(1);
  const [resetKey, setResetKey] = useState(0);
  const [creating, setCreating] = useState(false);
  const mayCreate = can("manage_quality") || Boolean(user?.memberships?.some((m) => m.is_lead));

  function update(patch: Partial<RiskFilters>) {
    setFilters({ ...filters, ...patch });
    setPage(1);
  }

  const matrix = useApiQuery<RiskMatrix>("/quality/risks/matrix/");
  const { rows, count, error, loading } = usePagedQuery<RiskItem>("/quality/risks/", riskQueryParams(filters, page, PAGE_SIZE));
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));
  const cell = filters.likelihood !== null && filters.impact !== null ? { likelihood: filters.likelihood, impact: filters.impact } : null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="ریسک‌ها"
        subtitle="مشکلاتی که هنوز رخ نداده‌اند: چقدر محتمل‌اند، چه اثری دارند و چه کاری برایشان می‌شود"
        actions={
          mayCreate && (
            <Button variant="primary" icon={<Plus />} onClick={() => setCreating(true)}>
              ثبت ریسک
            </Button>
          )
        }
      />

      <div className="grid gap-6 lg:grid-cols-[22rem_minmax(0,1fr)]">
        <Card aria-label="نقشهٔ حرارتی ریسک" className="self-start">
          <CardHeader
            title="نقشهٔ ریسک"
            description={matrix.data ? `${toPersianDigits(matrix.data.total)} ریسک باز` : undefined}
            icon={<Grid3x3 />}
          />
          {matrix.loading ? (
            <SkeletonLines rows={5} />
          ) : matrix.error || !matrix.data ? (
            <ErrorBanner message={matrix.error ?? "دریافت نقشه ممکن نشد."} />
          ) : (
            <RiskHeatMap matrix={matrix.data} selected={cell} onSelect={(picked) => update({ likelihood: picked?.likelihood ?? null, impact: picked?.impact ?? null })} />
          )}
          <p className="mt-3 text-xs leading-6 text-slate-500">ریسک‌های بسته‌شده در نقشه شمرده نمی‌شوند. با زدن یک خانه، فهرست به همان خانه محدود می‌شود.</p>
        </Card>

        <div className="min-w-0 space-y-4">
          <Card as="section" className="flex flex-wrap items-center gap-2 p-3 sm:gap-3 sm:p-4">
            <DebouncedInput
              key={resetKey}
              value={filters.q}
              onCommit={(q) => update({ q })}
              placeholder="جست و جوی عنوان، شرح یا کد (RK-0013)"
              ariaLabel="جست و جوی ریسک"
            />
            <select aria-label="وضعیت" value={filters.status} onChange={(e) => update({ status: e.target.value as RiskStatus | "" })} className={select}>
              <option value="">همهٔ وضعیت‌ها</option>
              {(Object.keys(RISK_STATUS_LABELS) as RiskStatus[]).map((value) => (
                <option key={value} value={value}>
                  {RISK_STATUS_LABELS[value]}
                </option>
              ))}
            </select>
            <select aria-label="سطح" value={filters.level} onChange={(e) => update({ level: e.target.value as RiskLevel | "" })} className={select}>
              <option value="">همهٔ سطح‌ها</option>
              {(Object.keys(RISK_LEVEL_LABELS) as RiskLevel[]).map((value) => (
                <option key={value} value={value}>
                  {RISK_LEVEL_LABELS[value]}
                </option>
              ))}
            </select>
            <select aria-label="مربوط به من" value={filters.mine} onChange={(e) => update({ mine: e.target.value as RiskMine })} className={select}>
              {MINE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <label className={toggle}>
              <input type="checkbox" className="size-4 rounded" checked={filters.reviewDue} onChange={(e) => update({ reviewDue: e.target.checked })} />
              زمان بازنگری رسیده
            </label>
            {cell && (
              <span className="inline-flex h-10 items-center gap-2 rounded-lg bg-slate-900 px-3 text-sm text-white">
                احتمال {toPersianDigits(cell.likelihood)} · اثر {toPersianDigits(cell.impact)}
                <button type="button" aria-label="برداشتن خانهٔ انتخاب‌شده" onClick={() => update({ likelihood: null, impact: null })} className="rounded-full p-0.5 hover:bg-white/20">
                  <X className="size-4" />
                </button>
              </span>
            )}
            {hasActiveRiskFilters(filters) && (
              <Button
                variant="ghost"
                size="sm"
                icon={<RotateCcw />}
                className="animate-fade-in"
                onClick={() => {
                  setFilters(EMPTY_RISK_FILTERS);
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
              icon={<Gauge />}
              message={hasActiveRiskFilters(filters) ? "ریسکی با این فیلترها پیدا نشد." : "هنوز ریسکی ثبت نشده یا شما حق دیدن آن را ندارید."}
            />
          ) : (
            <Card flush>
              <ul className="divide-y divide-slate-100">
                {rows.map((risk) => (
                  <RiskListItem key={risk.id} risk={risk} />
                ))}
              </ul>
            </Card>
          )}

          <Pager page={page} totalPages={totalPages} onChange={setPage} />
        </div>
      </div>

      {creating && (
        <RiskFormDialog
          onSaved={(saved) => {
            setCreating(false);
            router.push(`/quality/risks/${saved.id}`);
          }}
          onClose={() => setCreating(false)}
        />
      )}
    </div>
  );
}
