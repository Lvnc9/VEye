import type { CSSProperties, ReactNode } from "react";
import Link from "next/link";
import { ArrowUpLeft } from "lucide-react";
import { NumberTicker } from "./NumberTicker";
import { Skeleton } from "./Skeleton";
import { cx } from "./cx";

type StatTone = "neutral" | "brand" | "success" | "warning" | "danger" | "info";

const TONES: Record<StatTone, { tile: string; glow: string }> = {
  neutral: { tile: "bg-slate-100 text-slate-600 ring-slate-500/10 dark:bg-white/[0.06] dark:text-slate-300", glow: "from-slate-400/15" },
  brand: { tile: "bg-sky-50 text-sky-700 ring-sky-600/15 dark:bg-sky-400/10 dark:text-sky-300", glow: "from-sky-400/25" },
  success: { tile: "bg-emerald-50 text-emerald-700 ring-emerald-600/15 dark:bg-emerald-400/10 dark:text-emerald-300", glow: "from-emerald-400/25" },
  warning: { tile: "bg-amber-50 text-amber-700 ring-amber-600/15 dark:bg-amber-400/10 dark:text-amber-300", glow: "from-amber-400/25" },
  danger: { tile: "bg-rose-50 text-rose-700 ring-rose-600/15 dark:bg-rose-400/10 dark:text-rose-300", glow: "from-rose-400/25" },
  info: { tile: "bg-indigo-50 text-indigo-700 ring-indigo-600/15 dark:bg-indigo-400/10 dark:text-indigo-300", glow: "from-indigo-400/25" },
};

/**
 * One headline number (after 21st.dev's «Stats Bento» / «Statistics Card»): a label, the number counting
 * up into view, an icon tile in the tone's colour with a soft glow of it behind, and an optional line under
 * the number and share bar. With `href` the whole card is a link that lifts on hover.
 */
export function StatCard({
  label,
  value,
  icon,
  tone = "neutral",
  hint,
  share,
  href,
  index = 0,
  className,
}: {
  label: ReactNode;
  /** null while loading. */
  value: number | null;
  icon: ReactNode;
  tone?: StatTone;
  hint?: ReactNode;
  /** 0–1: a thin bar under the number (this number's part of a whole). */
  share?: number | null;
  href?: string;
  /** Position in a staggered entrance. */
  index?: number;
  className?: string;
}) {
  const { tile, glow } = TONES[tone];
  const body = (
    <>
      <span aria-hidden className={cx("pointer-events-none absolute -top-10 -left-10 size-32 rounded-full bg-gradient-to-br to-transparent blur-2xl", glow)} />
      <div className="relative flex items-start justify-between gap-3">
        <p className="text-sm text-muted-foreground">{label}</p>
        <span className={cx("flex size-9 shrink-0 items-center justify-center rounded-xl ring-1 ring-inset [&_svg]:size-[18px]", tile)}>{icon}</span>
      </div>
      {value === null ? (
        <Skeleton className="relative mt-3 h-9 w-16" />
      ) : (
        <p className="relative mt-2 text-3xl font-black leading-10 tracking-tight text-foreground">
          <NumberTicker value={value} />
        </p>
      )}
      {share != null && (
        <div className="relative mt-3 h-1 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full w-full origin-right rounded-full bg-current transition-transform duration-1000 ease-out-quint"
            style={{ transform: `scaleX(${Math.max(0, Math.min(1, share))})`, color: "var(--primary)" }}
          />
        </div>
      )}
      {hint && <p className="relative mt-2 text-xs text-muted-foreground">{hint}</p>}
      {href && (
        <ArrowUpLeft
          aria-hidden
          className="absolute bottom-4 left-4 size-4 text-subtle-foreground opacity-0 transition-[opacity,translate] duration-200 group-hover:-translate-x-0.5 group-hover:-translate-y-0.5 group-hover:opacity-100"
        />
      )}
    </>
  );
  const classes = cx(
    "veye-stagger group relative block overflow-hidden rounded-2xl border border-border bg-card p-4 shadow-card sm:p-5",
    href && "transition-[box-shadow,border-color,translate] duration-200 ease-out-quint hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-raised dark:hover:border-white/15",
    className,
  );
  const style = { "--i": index } as CSSProperties;
  return href ? (
    <Link href={href} className={classes} style={style}>
      {body}
    </Link>
  ) : (
    <div className={classes} style={style}>
      {body}
    </div>
  );
}
