import Link from "next/link";
import { AlarmClock, Building2, CalendarClock, UserRound, UserX } from "lucide-react";
import { Code } from "@/components/Code";
import { RiskLevelBadge, RiskStatusBadge } from "@/components/quality/Badges";
import { formatJalali, toPersianDigits } from "@/lib/jalali";
import type { RiskItem } from "@/lib/quality";

/** One row of the register: code, title, level with its score, status, node, owner and review date (red
 *  once it has passed). The whole row is the link. */
export function RiskListItem({ risk }: { risk: RiskItem }) {
  return (
    <li>
      <Link
        href={`/quality/risks/${risk.id}`}
        className="block space-y-2.5 px-4 py-3.5 transition-colors hover:bg-slate-50 focus-visible:bg-slate-50 sm:px-5"
      >
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <Code>{risk.code}</Code>
          <span className="min-w-0 flex-1 basis-48 font-bold text-slate-900">{risk.title}</span>
          <span className="flex flex-wrap items-center gap-1.5">
            <RiskLevelBadge level={risk.level} label={risk.level_label} score={toPersianDigits(risk.score)} />
            <RiskStatusBadge status={risk.status} label={risk.status_label} />
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
          <span className="inline-flex items-center gap-1">
            <Building2 className="size-3.5" />
            {risk.owner_node_name}
          </span>
          <span className="inline-flex items-center gap-1">
            {risk.owner_is_active === false ? <UserX className="size-3.5 text-amber-600" /> : <UserRound className="size-3.5" />}
            {risk.owner_name ?? "بدون مسئول"}
            {risk.owner_is_active === false && <span className="text-amber-700">(غیرفعال)</span>}
          </span>
          {risk.review_on && (
            <span className={risk.review_overdue ? "inline-flex items-center gap-1 font-bold text-rose-700" : "inline-flex items-center gap-1"}>
              {risk.review_overdue ? <AlarmClock className="size-3.5" /> : <CalendarClock className="size-3.5" />}
              بازنگری: {formatJalali(risk.review_on)}
            </span>
          )}
        </div>
      </Link>
    </li>
  );
}
