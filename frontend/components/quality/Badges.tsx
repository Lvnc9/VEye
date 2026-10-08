import { Badge } from "@/components/ui/Badge";
import { cx } from "@/components/ui/cx";
import {
  AUDIT_STATUS_TONE,
  RISK_LEVEL_STYLE,
  RISK_STATUS_TONE,
  type RiskLevel,
  type RiskStatus,
  NC_SEVERITY_TONE,
  NC_STATUS_TONE,
  type AuditStatus,
  type NcSeverity,
  type NcStatus,
} from "@/lib/quality";

export function NcStatusBadge({ status, label }: { status: NcStatus; label: string }) {
  return (
    <Badge tone={NC_STATUS_TONE[status]} dot>
      {label}
    </Badge>
  );
}

export function SeverityBadge({ severity, label }: { severity: NcSeverity; label: string }) {
  return <Badge tone={NC_SEVERITY_TONE[severity]}>{label}</Badge>;
}

export function AuditStatusBadge({ status, label }: { status: AuditStatus; label: string }) {
  return (
    <Badge tone={AUDIT_STATUS_TONE[status]} dot>
      {label}
    </Badge>
  );
}

export function RiskStatusBadge({ status, label }: { status: RiskStatus; label: string }) {
  return (
    <Badge tone={RISK_STATUS_TONE[status]} dot>
      {label}
    </Badge>
  );
}

/** The level in the heat map's own colour, with the score: «زیاد · ۱۲». */
export function RiskLevelBadge({ level, label, score }: { level: RiskLevel; label: string; score?: string }) {
  return (
    <span className={cx("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-bold ring-1 ring-inset", RISK_LEVEL_STYLE[level].chip)}>
      {label}
      {score && <span className="font-normal">· {score}</span>}
    </span>
  );
}
