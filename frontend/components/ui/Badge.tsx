import type { ReactNode } from "react";
import { cx } from "./cx";

/** The one tone vocabulary of every status pill in the app. */
export type Tone = "neutral" | "brand" | "success" | "warning" | "danger" | "info" | "violet";

export const TONE_BADGE: Record<Tone, string> = {
  neutral: "bg-slate-100 text-slate-700 ring-slate-500/15",
  brand: "bg-brand-50 text-brand-800 ring-brand-600/20",
  success: "bg-emerald-50 text-emerald-800 ring-emerald-600/20",
  warning: "bg-amber-50 text-amber-800 ring-amber-600/25",
  danger: "bg-rose-50 text-rose-800 ring-rose-600/20",
  info: "bg-indigo-50 text-indigo-800 ring-indigo-600/20",
  violet: "bg-violet-50 text-violet-800 ring-violet-600/20",
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
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs ring-1 ring-inset",
        TONE_BADGE[tone],
        className,
      )}
    >
      {dot && <span aria-hidden className={cx("size-1.5 rounded-full", TONE_DOT[tone])} />}
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
        "inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-rose-600 px-1.5 text-[11px] font-bold leading-none text-white tabular-nums shadow-sm",
        className,
      )}
    >
      {children}
    </span>
  );
}
