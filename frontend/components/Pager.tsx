"use client";

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
  const button = "rounded border border-slate-300 bg-white px-3 py-1.5 disabled:opacity-40";
  return (
    <nav className="flex items-center justify-center gap-4 text-sm" aria-label="صفحه‌بندی">
      <button type="button" onClick={() => onChange(page - 1)} disabled={page <= 1} className={button}>
        قبلی
      </button>
      <span className="text-slate-600">
        صفحه {page} از {totalPages}
      </span>
      <button type="button" onClick={() => onChange(page + 1)} disabled={page >= totalPages} className={button}>
        بعدی
      </button>
    </nav>
  );
}
