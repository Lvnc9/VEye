import Link from "next/link";
import { formatJalali } from "@/lib/jalali";
import { actionsProgress, actionsSummary, type NonConformance } from "@/lib/quality";
import { toPersianDigits } from "@/lib/jalali";
import { AlarmClock, Building2, UserRound } from "lucide-react";
import { Code } from "@/components/Code";
import { NcStatusBadge, SeverityBadge } from "@/components/quality/Badges";
import { ProgressBar } from "@/components/ui/ProgressBar";

/** One row of the list: the code, the title, what it is and how far along, and who/where/when. The whole
 *  row is the link, so a thumb finds it as easily as a mouse. */
export function NcListItem({ nc }: { nc: NonConformance }) {
  const progress = actionsProgress(nc);
  return (
    <li>
      <Link
        href={`/quality/${nc.id}`}
        className="block space-y-2.5 px-4 py-3.5 transition-colors hover:bg-slate-50 focus-visible:bg-slate-50 sm:px-5"
      >
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <Code>{nc.code}</Code>
          <span className="min-w-0 flex-1 basis-48 font-bold text-slate-900">{nc.title}</span>
          <span className="flex flex-wrap items-center gap-1.5">
            <SeverityBadge severity={nc.severity} label={nc.severity_label} />
            <NcStatusBadge status={nc.status} label={nc.status_label} />
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
          <span className="inline-flex items-center gap-1">
            <Building2 className="size-3.5" />
            {nc.owner_node_name}
          </span>
          <span className="inline-flex items-center gap-1">
            <UserRound className="size-3.5" />
            {nc.reported_by_name}
          </span>
          <span>کشف: {formatJalali(nc.detected_on)}</span>
          <span>{nc.source_label}</span>
        </div>
        {nc.status === "IN_PROGRESS" && (
          <div className="flex flex-wrap items-center gap-3">
            <ProgressBar value={progress} className="h-1.5 w-40" label="پیشرفت اقدام‌ها" />
            <span className="text-xs text-slate-600">{actionsSummary(nc)}</span>
            {nc.actions_overdue > 0 && (
              <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-xs text-rose-800 ring-1 ring-inset ring-rose-600/20">
                <AlarmClock className="size-3.5" />
                {toPersianDigits(nc.actions_overdue)} اقدام دیرکرد
              </span>
            )}
          </div>
        )}
      </Link>
    </li>
  );
}
