"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/Button";

/** Previous / next with «صفحه X از Y», as on the register. Renders nothing for one page. */
export function Pager({
  page,
  totalPages,
  onChange,
}: {
  page: number;
  totalPages: number;
  onChange: (page: number) => void;
}) {
  if (totalPages <= 1) return null;
  return (
    <nav className="flex items-center justify-center gap-3 text-sm" aria-label="صفحه‌بندی">
      <Button size="sm" onClick={() => onChange(page - 1)} disabled={page <= 1} icon={<ChevronRight />}>
        قبلی
      </Button>
      <span className="min-w-24 text-center text-slate-600 tabular-nums">
        صفحه {page} از {totalPages}
      </span>
      <Button size="sm" onClick={() => onChange(page + 1)} disabled={page >= totalPages}>
        بعدی
        <ChevronLeft />
      </Button>
    </nav>
  );
}
