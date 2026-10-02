import { Badge } from "@/components/ui/Badge";
import {
  NC_SEVERITY_TONE,
  NC_STATUS_TONE,
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
