import { Badge } from "@/components/ui/Badge";
import {
  AUDIT_STATUS_TONE,
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
