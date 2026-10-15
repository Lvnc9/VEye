import type { ReactNode } from "react";
import { Inbox } from "lucide-react";
import { cx } from "./cx";

/**
 * Nothing to show yet: an icon in soft concentric rings, what is missing, and optionally what to do about
 * it (after 21st.dev's «Empty» blocks by shadcn and uiable — the rings are decorative CSS).
 */
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
        "relative isolate flex flex-col items-center justify-center overflow-hidden rounded-2xl border border-dashed border-input",
        "bg-[radial-gradient(ellipse_at_top,color-mix(in_oklch,var(--primary)_7%,transparent),transparent_65%)] text-center animate-fade-in",
        compact ? "gap-2 px-4 py-6" : "gap-3 px-6 py-12",
        className,
      )}
    >
      <span className="relative flex items-center justify-center">
        {!compact && (
          <>
            <span aria-hidden className="absolute size-28 rounded-full border border-border/70" />
            <span aria-hidden className="absolute size-20 rounded-full border border-border" />
          </>
        )}
        <span
          className={cx(
            "relative flex items-center justify-center rounded-2xl bg-card text-muted-foreground shadow-card ring-1 ring-border",
            compact ? "size-10 [&_svg]:size-5" : "size-12 [&_svg]:size-6",
          )}
        >
          {icon ?? <Inbox />}
        </span>
      </span>
      {title && <p className={cx("text-sm font-bold text-foreground", !compact && "mt-3")}>{title}</p>}
      {message && <p className="max-w-md text-sm leading-7 text-muted-foreground">{message}</p>}
      {action && <div className="pt-1">{action}</div>}
    </div>
  );
}
