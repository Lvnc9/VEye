import type { ReactNode } from "react";
import { Inbox } from "lucide-react";
import { cx } from "./cx";

/** Nothing to show yet: a soft icon, what is missing, and optionally what to do about it. */
export function EmptyState({
  title,
  message,
  icon,
  action,
  compact = false,
  className,
}: {
  title?: ReactNode;
  message?: ReactNode;
  icon?: ReactNode;
  action?: ReactNode;
  compact?: boolean;
  className?: string;
}) {
  return (
    <div
      className={cx(
        "flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white/60 text-center animate-fade-in",
        compact ? "gap-2 px-4 py-6" : "gap-3 px-6 py-10",
        className,
      )}
    >
      <span
        className={cx(
          "flex items-center justify-center rounded-2xl bg-slate-100 text-slate-400 ring-1 ring-slate-200",
          compact ? "size-10 [&_svg]:size-5" : "size-12 [&_svg]:size-6",
        )}
      >
        {icon ?? <Inbox />}
      </span>
      {title && <p className="text-sm font-bold text-slate-800">{title}</p>}
      {message && <p className="max-w-md text-sm leading-7 text-slate-500">{message}</p>}
      {action && <div className="pt-1">{action}</div>}
    </div>
  );
}
