import { cx } from "./cx";

/** A grey placeholder with a light band sweeping across it, the shape of what is loading. */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cx("veye-skeleton h-4", className)} />;
}

/** A few rows of placeholder text — the default shape of «در حال بارگذاری». */
export function SkeletonLines({ rows = 3, className }: { rows?: number; className?: string }) {
  const widths = ["w-11/12", "w-8/12", "w-10/12", "w-7/12", "w-9/12"];
  return (
    <div aria-hidden className={cx("space-y-3", className)}>
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className={cx("h-3.5", widths[i % widths.length])} />
      ))}
    </div>
  );
}
