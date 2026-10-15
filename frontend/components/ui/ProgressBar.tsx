import { cx } from "./cx";

/** A thin bar that fills from the start edge (the right, in RTL). The fill scales rather than resizes,
 *  so a change animates smoothly. */
export function ProgressBar({
  value,
  tone = "bg-gradient-to-l from-sky-500 to-brand-600 dark:from-sky-300 dark:to-sky-500",
  className,
  label,
}: {
  /** 0–100; null draws an empty track. */
  value: number | null;
  tone?: string;
  className?: string;
  label?: string;
}) {
  const ratio = Math.max(0, Math.min(100, value ?? 0)) / 100;
  return (
    <div
      role={label ? "progressbar" : "presentation"}
      aria-label={label}
      aria-valuenow={label && value !== null ? value : undefined}
      aria-valuemin={label ? 0 : undefined}
      aria-valuemax={label ? 100 : undefined}
      className={cx("h-2 overflow-hidden rounded-full bg-muted", className)}
    >
      <div
        className={cx("h-full w-full origin-right rounded-full transition-transform duration-700 ease-out-quint", tone)}
        style={{ transform: `scaleX(${ratio})` }}
      />
    </div>
  );
}
