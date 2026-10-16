"use client";

import { Wallet } from "lucide-react";
import { toPersianDigits } from "@/lib/jalali";
import { signedDays, type BalanceResponse } from "@/lib/leave";
import { useApiQuery } from "@/lib/use-api-query";
import { Card, CardHeader } from "@/components/ui/Card";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { cx } from "@/components/ui/cx";

/** «مانده مرخصی من» (Phase 22): this Jalali year's annual-leave balance — entitlement, carried over, used,
 *  waiting for a decision, and what is left. Nothing shows for a year before balances were kept. */
export function MyBalanceCard({ reload }: { reload: number }) {
  const data = useApiQuery<BalanceResponse>("/leave/balance/", reload).data;
  if (!data?.tracked || !data.balance) return null;
  const b = data.balance;
  const total = b.entitlement + b.carried;
  const usedShare = total > 0 ? Math.min(100, Math.round((100 * (b.used + b.pending)) / total)) : 100;
  const stats: [string, string, string?][] = [
    ["سهم سال", toPersianDigits(b.entitlement)],
    ["منتقل‌شده از سال قبل", toPersianDigits(b.carried)],
    ["استفاده‌شده", toPersianDigits(b.used)],
    ["در انتظار تصمیم", toPersianDigits(b.pending)],
  ];
  return (
    <Card aria-label="مانده مرخصی من">
      <CardHeader
        title={`مانده مرخصی استحقاقی من — ${toPersianDigits(b.year)}`}
        icon={<Wallet />}
        description={`روز کاری؛ تا ${toPersianDigits(data.policy.carry_max)} روز مانده به سال بعد منتقل می‌شود`}
      />
      <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
        <div>
          <p className={cx("text-3xl font-bold tabular-nums", b.remaining < 0 ? "text-destructive" : "text-foreground")}>
            {signedDays(b.remaining)}
          </p>
          <p className="text-xs text-muted-foreground">روز مانده</p>
        </div>
        <dl className="grid flex-1 grid-cols-2 gap-3 sm:grid-cols-4">
          {stats.map(([label, value]) => (
            <div key={label}>
              <dt className="text-xs text-muted-foreground">{label}</dt>
              <dd className="font-bold tabular-nums text-foreground">{value}</dd>
            </div>
          ))}
        </dl>
      </div>
      <ProgressBar value={usedShare} label="سهم مصرف‌شده" className="mt-4" />
    </Card>
  );
}
