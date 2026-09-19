import type { DocumentStatus } from "@/lib/types";

const STYLES: Record<DocumentStatus, string> = {
  DRAFT: "bg-slate-100 text-slate-700",
  AWAITING_CONFIRMATION: "bg-amber-100 text-amber-800",
  AWAITING_APPROVAL: "bg-orange-100 text-orange-800",
  UNDER_CONTROL: "bg-green-100 text-green-800",
  OBSOLETE: "bg-red-100 text-red-800",
};

export function StatusBadge({ status, label }: { status: DocumentStatus; label: string }) {
  return (
    <span className={`whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ${STYLES[status]}`}>
      {label}
    </span>
  );
}
