import type { DocumentStatus } from "@/lib/types";
import { Badge, type Tone } from "@/components/ui/Badge";

/** Draft → awaiting confirmation → awaiting approval → under control; obsolete is the dead end. */
export const DOCUMENT_STATUS_TONE: Record<DocumentStatus, Tone> = {
  DRAFT: "neutral",
  AWAITING_CONFIRMATION: "warning",
  AWAITING_APPROVAL: "brand",
  UNDER_CONTROL: "success",
  OBSOLETE: "danger",
};

export function StatusBadge({ status, label }: { status: DocumentStatus; label: string }) {
  return (
    <Badge tone={DOCUMENT_STATUS_TONE[status]} dot>
      {label}
    </Badge>
  );
}
