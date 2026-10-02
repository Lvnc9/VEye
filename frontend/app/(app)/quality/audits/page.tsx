"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ClipboardCheck, Plus, RotateCcw } from "lucide-react";
import { DebouncedInput } from "@/components/history/DebouncedInput";
import { AuditFormDialog } from "@/components/quality/AuditFormDialog";
import { AuditListItem } from "@/components/quality/AuditListItem";
import { Pager } from "@/components/Pager";
import { ErrorBanner } from "@/components/StatusBanner";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { selectClass } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { cx } from "@/components/ui/cx";
import { useCurrentUser } from "@/lib/current-user";
import { todayIso } from "@/lib/jalali";
import {
  AUDIT_STATUS_LABELS,
  EMPTY_AUDIT_FILTERS,
  auditQueryParams,
  hasActiveAuditFilters,
  type AuditFilters,
  type AuditMine,
  type AuditStatus,
  type InternalAudit,
} from "@/lib/quality";
import { usePagedQuery } from "@/lib/use-paged-query";

const PAGE_SIZE = 20;
const select = cx(selectClass, "min-w-[8rem] flex-1 sm:flex-none");

const MINE_OPTIONS: { value: AuditMine; label: string }[] = [
  { value: "", label: "همهٔ ممیزی‌هایی که می‌بینم" },
  { value: "auditor", label: "ممیزی‌هایی که ممیز اصلی آن‌ها هستم" },
  { value: "manage", label: "در حوزهٔ مسئولیت من" },
];

/** «ممیزی‌های داخلی» (Phase 18): the audits the viewer may read — they lead one, lead the audited unit or
 *  one above it, or manage quality. Only a quality manager plans one, so the button is theirs alone. */
export default function AuditsPage() {
  const router = useRouter();
  const { can } = useCurrentUser();
  const today = useMemo(() => todayIso(), []);
  const [filters, setFilters] = useState<AuditFilters>(EMPTY_AUDIT_FILTERS);
  const [page, setPage] = useState(1);
  const [resetKey, setResetKey] = useState(0);
  const [planning, setPlanning] = useState(false);

  function update(patch: Partial<AuditFilters>) {
    setFilters({ ...filters, ...patch });
    setPage(1);
  }

  const { rows, count, error, loading } = usePagedQuery<InternalAudit>("/quality/audits/", auditQueryParams(filters, page, PAGE_SIZE));
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <PageHeader
        title="ممیزی‌های داخلی"
        subtitle="بررسی‌های برنامه‌ریزی‌شدهٔ بخش‌های سازمان و یافته‌های آن‌ها"
        actions={
          can("manage_quality") && (
            <Button variant="primary" icon={<Plus />} onClick={() => setPlanning(true)}>
              برنامه‌ریزی ممیزی
            </Button>
          )
        }
      />

      <Card as="section" className="flex flex-wrap items-center gap-2 p-3 sm:gap-3 sm:p-4">
        <DebouncedInput
          key={resetKey}
          value={filters.q}
          onCommit={(q) => update({ q })}
          placeholder="جست و جوی عنوان یا کد (AU-0007)"
          ariaLabel="جست و جوی ممیزی"
        />
        <select aria-label="وضعیت" value={filters.status} onChange={(e) => update({ status: e.target.value as AuditStatus | "" })} className={select}>
          <option value="">همهٔ وضعیت‌ها</option>
          {(Object.keys(AUDIT_STATUS_LABELS) as AuditStatus[]).map((value) => (
            <option key={value} value={value}>
              {AUDIT_STATUS_LABELS[value]}
            </option>
          ))}
        </select>
        <select aria-label="مربوط به من" value={filters.mine} onChange={(e) => update({ mine: e.target.value as AuditMine })} className={select}>
          {MINE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        {hasActiveAuditFilters(filters) && (
          <Button
            variant="ghost"
            size="sm"
            icon={<RotateCcw />}
            className="animate-fade-in"
            onClick={() => {
              setFilters(EMPTY_AUDIT_FILTERS);
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
          icon={<ClipboardCheck />}
          message={hasActiveAuditFilters(filters) ? "ممیزی‌ای با این فیلترها پیدا نشد." : "هنوز ممیزی‌ای برنامه‌ریزی نشده یا شما حق دیدن آن را ندارید."}
        />
      ) : (
        <Card flush>
          <ul className="divide-y divide-slate-100">
            {rows.map((audit) => (
              <AuditListItem key={audit.id} audit={audit} today={today} />
            ))}
          </ul>
        </Card>
      )}

      <Pager page={page} totalPages={totalPages} onChange={setPage} />

      {planning && (
        <AuditFormDialog
          onSaved={(saved) => {
            setPlanning(false);
            router.push(`/quality/audits/${saved.id}`);
          }}
          onClose={() => setPlanning(false)}
        />
      )}
    </div>
  );
}
