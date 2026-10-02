import Link from "next/link";
import { AlarmClock, Building2, CalendarClock, UserRound, UserX } from "lucide-react";
import { Code } from "@/components/Code";
import { AuditStatusBadge } from "@/components/quality/Badges";
import { formatJalali } from "@/lib/jalali";
import { auditIsLate, findingsSummary, type InternalAudit } from "@/lib/quality";

/** One row of the audit list: the code, the title and status, the audited node, the auditor, the planned
 *  date and what it found. The whole row is the link. `today` is passed in (one date for the whole list). */
export function AuditListItem({ audit, today }: { audit: InternalAudit; today: string }) {
  return (
    <li>
      <Link
        href={`/quality/audits/${audit.id}`}
        className="block space-y-2.5 px-4 py-3.5 transition-colors hover:bg-slate-50 focus-visible:bg-slate-50 sm:px-5"
      >
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <Code>{audit.code}</Code>
          <span className="min-w-0 flex-1 basis-48 font-bold text-slate-900">{audit.title}</span>
          <span className="flex flex-wrap items-center gap-1.5">
            {auditIsLate(audit, today) && (
              <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-xs text-rose-800 ring-1 ring-inset ring-rose-600/20">
                <AlarmClock className="size-3.5" />
                از تاریخ برنامه گذشته
              </span>
            )}
            <AuditStatusBadge status={audit.status} label={audit.status_label} />
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
          <span className="inline-flex items-center gap-1">
            <Building2 className="size-3.5" />
            {audit.scope_node_name}
          </span>
          <span className="inline-flex items-center gap-1">
            {audit.lead_auditor_is_active ? <UserRound className="size-3.5" /> : <UserX className="size-3.5 text-amber-600" />}
            {audit.lead_auditor_name}
            {!audit.lead_auditor_is_active && <span className="text-amber-700">(غیرفعال)</span>}
          </span>
          <span className="inline-flex items-center gap-1">
            <CalendarClock className="size-3.5" />
            {formatJalali(audit.planned_on)}
          </span>
          <span>{findingsSummary(audit)}</span>
        </div>
      </Link>
    </li>
  );
}
