"use client";

import { useState } from "react";
import { Pencil } from "lucide-react";
import { ApiError, apiPut } from "@/lib/api-client";
import { jalaliOf, toPersianDigits } from "@/lib/jalali";
import { balanceYears, parseEntitlement, signedDays, type BalancesRow, type LeavePolicy } from "@/lib/leave";
import { useApiQuery } from "@/lib/use-api-query";
import { usePagedQuery } from "@/lib/use-paged-query";
import { Pager } from "@/components/Pager";
import { ErrorBanner } from "@/components/StatusBanner";
import { Avatar } from "@/components/ui/Avatar";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Dialog, DialogFooter } from "@/components/ui/Dialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { Field, inputClass, selectClass } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { cx } from "@/components/ui/cx";

const PAGE_SIZE = 25;

/** «مانده مرخصی» for HR and the مدیر عامل (Phase 22): everyone's annual-leave balance for a Jalali year, and a way
 *  to set one person's entitlement for it — a different contract, or their opening balance in the first year. */
export function BalancesTab({ canEdit }: { canEdit: boolean }) {
  const currentYear = jalaliOf(new Date()).jy;
  const policy = useApiQuery<LeavePolicy>("/leave/policy/").data;
  const [year, setYear] = useState(currentYear);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [reload, setReload] = useState(0);
  const [editing, setEditing] = useState<BalancesRow | null>(null);
  const { rows, count, error, loading } = usePagedQuery<BalancesRow>(
    "/leave/balances/",
    { year, q: search, page, page_size: PAGE_SIZE },
    reload,
  );
  const years = balanceYears(policy?.start_year ?? currentYear, currentYear);
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  return (
    <div className="space-y-4">
      <Card as="section" className="flex flex-wrap items-center gap-3 p-3 sm:p-4">
        <select
          aria-label="سال"
          value={year}
          onChange={(e) => {
            setYear(Number(e.target.value));
            setPage(1);
          }}
          className={cx(selectClass, "w-32")}
        >
          {years.map((y) => (
            <option key={y} value={y}>
              {toPersianDigits(y)}
            </option>
          ))}
        </select>
        <input
          type="search"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          placeholder="جست‌وجوی نام"
          aria-label="جست‌وجوی نام"
          className={cx(inputClass, "w-full sm:w-64")}
        />
        {policy && (
          <span className="text-xs text-muted-foreground">
            سهم پیش‌فرض {toPersianDigits(policy.annual_days)} روز کاری، انتقال تا {toPersianDigits(policy.carry_max)} روز؛ محاسبه از
            سال {toPersianDigits(policy.start_year)}
          </span>
        )}
      </Card>

      {loading ? (
        <Skeleton className="h-40 w-full" />
      ) : error ? (
        <ErrorBanner message={error} />
      ) : rows.length === 0 ? (
        <EmptyState message="کسی پیدا نشد." />
      ) : (
        <Card flush>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[40rem] text-sm">
              <thead className="border-b border-border text-xs text-muted-foreground">
                <tr>
                  {["نام", "سهم", "منتقل‌شده", "استفاده‌شده", "در انتظار", "مانده", ""].map((h, i) => (
                    <th key={i} className="px-3 py-2.5 text-start font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map((row) => (
                  <tr key={row.user.id}>
                    <td className="px-3 py-2.5">
                      <span className="inline-flex items-center gap-2">
                        <Avatar name={row.user.full_name} size="sm" />
                        <span>
                          <span className="block font-bold text-foreground">{row.user.full_name}</span>
                          <span className="block text-xs text-muted-foreground">{row.user.title}</span>
                        </span>
                      </span>
                    </td>
                    {row.balance ? (
                      <>
                        <td className="px-3 py-2.5 tabular-nums">
                          {toPersianDigits(row.balance.entitlement)}
                          {row.has_override && (
                            <Badge tone="info" className="ms-1.5" title="مقدار ویژهٔ تعیین‌شده توسط منابع انسانی">
                              ویژه
                            </Badge>
                          )}
                        </td>
                        <td className="px-3 py-2.5 tabular-nums">{toPersianDigits(row.balance.carried)}</td>
                        <td className="px-3 py-2.5 tabular-nums">{toPersianDigits(row.balance.used)}</td>
                        <td className="px-3 py-2.5 tabular-nums">{toPersianDigits(row.balance.pending)}</td>
                        <td className={cx("px-3 py-2.5 font-bold tabular-nums", row.balance.remaining < 0 && "text-destructive")}>
                          {signedDays(row.balance.remaining)}
                        </td>
                      </>
                    ) : (
                      <td colSpan={5} className="px-3 py-2.5 text-muted-foreground">
                        پیش از آغاز محاسبهٔ مانده
                      </td>
                    )}
                    <td className="px-3 py-2.5 text-end">
                      {canEdit && row.balance && (
                        <Button size="xs" variant="ghost" icon={<Pencil />} onClick={() => setEditing(row)}>
                          تعیین سهم
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      <Pager page={page} totalPages={totalPages} onChange={setPage} />

      {editing && (
        <EntitlementDialog
          row={editing}
          year={year}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            setReload((n) => n + 1);
          }}
        />
      )}
    </div>
  );
}

function EntitlementDialog({ row, year, onClose, onSaved }: { row: BalancesRow; year: number; onClose: () => void; onSaved: () => void }) {
  const [text, setText] = useState(row.has_override && row.balance ? String(row.balance.entitlement) : "");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const parsed = parseEntitlement(text);

  async function save() {
    if (parsed === "invalid") {
      setError("یک عدد صحیح از ۰ تا ۱۲۰ بنویسید، یا خالی بگذارید تا سهم پیش‌فرض اعمال شود.");
      return;
    }
    setSending(true);
    setError(null);
    try {
      await apiPut("/leave/entitlements/", { user: row.user.id, year, days: parsed });
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ذخیره نشد. دوباره تلاش کنید.");
      setSending(false);
    }
  }

  return (
    <Dialog
      label="تعیین سهم مرخصی"
      title={`سهم مرخصی ${row.user.full_name} — ${toPersianDigits(year)}`}
      description="تعداد روز کاری مرخصی استحقاقی این سال. برای سال نخست محاسبه، همان مانده‌ای است که از پیش داشته است. خالی بگذارید تا سهم پیش‌فرض شرکت اعمال شود."
      onClose={onClose}
      busy={sending}
    >
      <Field label="سهم (روز کاری)" htmlFor="entitlement" hint="خالی = سهم پیش‌فرض">
        <input
          id="entitlement"
          inputMode="numeric"
          value={text}
          onChange={(e) => setText(e.target.value.replace(/[۰-۹]/g, (d) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(d))))}
          className={inputClass}
          dir="ltr"
        />
      </Field>
      {error && <ErrorBanner message={error} />}
      <DialogFooter>
        <Button onClick={onClose} disabled={sending}>
          انصراف
        </Button>
        <Button variant="primary" onClick={() => void save()} loading={sending}>
          ذخیره
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
