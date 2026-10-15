import type { ReactNode } from "react";
import { cx } from "./cx";

/** The one tone vocabulary of every status pill in the app. */
export type Tone = "neutral" | "brand" | "success" | "warning" | "danger" | "info" | "violet";

export const TONE_BADGE: Record<Tone, string> = {
  neutral: "bg-slate-100 text-slate-700 ring-slate-500/15 dark:bg-white/[0.06] dark:text-slate-300 dark:ring-white/10",
  brand: "bg-brand-50 text-brand-800 ring-brand-600/20 dark:bg-sky-400/10 dark:text-sky-300 dark:ring-sky-400/20",
  success: "bg-emerald-50 text-emerald-800 ring-emerald-600/20 dark:bg-emerald-400/10 dark:text-emerald-300 dark:ring-emerald-400/20",
  warning: "bg-amber-50 text-amber-800 ring-amber-600/25 dark:bg-amber-400/10 dark:text-amber-300 dark:ring-amber-400/20",
  danger: "bg-rose-50 text-rose-800 ring-rose-600/20 dark:bg-rose-400/10 dark:text-rose-300 dark:ring-rose-400/20",
  info: "bg-indigo-50 text-indigo-800 ring-indigo-600/20 dark:bg-indigo-400/10 dark:text-indigo-300 dark:ring-indigo-400/20",
  violet: "bg-violet-50 text-violet-800 ring-violet-600/20 dark:bg-violet-400/10 dark:text-violet-300 dark:ring-violet-400/20",
};

export const TONE_DOT: Record<Tone, string> = {
  neutral: "bg-slate-400",
  brand: "bg-brand-500",
  success: "bg-emerald-500",
  warning: "bg-amber-500",
  danger: "bg-rose-500",
  info: "bg-indigo-500",
  violet: "bg-violet-500",
};

export function Badge({
  tone = "neutral",
  dot = false,
  className,
  title,
  children,
}: {
  tone?: Tone;
  dot?: boolean;
  className?: string;
  title?: string;
  children: ReactNode;
}) {
  return (
    <span
      title={title}
      className={cx(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset",
        TONE_BADGE[tone],
        className,
      )}
    >
      {dot && (
        <span aria-hidden className="relative flex size-1.5">
          <span className={cx("size-1.5 rounded-full", TONE_DOT[tone])} />
        </span>
      )}
      {children}
    </span>
  );
}

/** A small red count, as on the کارتابل entry. */
export function CountBadge({ children, label, className }: { children: ReactNode; label?: string; className?: string }) {
  return (
    <span
      aria-label={label}
      className={cx(
        "inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-rose-600 px-1.5 text-[11px] font-bold leading-none text-white tabular-nums",
        "shadow-[0_0_0_2px_var(--card),0_2px_8px_-2px_rgb(225_29_72/0.6)]",
        className,
      )}
    >
      {children}
    </span>
  );
}
