import type { ReactNode } from "react";
import { CircleAlert, CircleCheck, Info, TriangleAlert } from "lucide-react";
import { cx } from "./cx";

type AlertTone = "info" | "success" | "warning" | "danger";

const TONES: Record<AlertTone, { box: string; icon: string; Icon: typeof Info }> = {
  info: {
    box: "border-brand-200 bg-brand-50/70 text-brand-900 dark:border-sky-400/20 dark:bg-sky-400/[0.07] dark:text-sky-100",
    icon: "bg-brand-100 text-brand-700 dark:bg-sky-400/15 dark:text-sky-300",
    Icon: Info,
  },
  success: {
    box: "border-emerald-200 bg-emerald-50/70 text-emerald-900 dark:border-emerald-400/20 dark:bg-emerald-400/[0.07] dark:text-emerald-100",
    icon: "bg-emerald-100 text-emerald-700 dark:bg-emerald-400/15 dark:text-emerald-300",
    Icon: CircleCheck,
  },
  warning: {
    box: "border-amber-200 bg-amber-50/80 text-amber-900 dark:border-amber-400/20 dark:bg-amber-400/[0.07] dark:text-amber-100",
    icon: "bg-amber-100 text-amber-700 dark:bg-amber-400/15 dark:text-amber-300",
    Icon: TriangleAlert,
  },
  danger: {
    box: "border-rose-200 bg-rose-50/80 text-rose-900 dark:border-rose-400/20 dark:bg-rose-400/[0.07] dark:text-rose-100",
    icon: "bg-rose-100 text-rose-700 dark:bg-rose-400/15 dark:text-rose-300",
    Icon: CircleAlert,
  },
};

/** A message in the flow of the page: an icon, an optional bold title, the text and optional actions. */
export function Alert({
  tone = "info",
  title,
  children,
  actions,
  role,
  className,
}: {
  tone?: AlertTone;
  title?: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
  role?: "alert" | "status";
  className?: string;
}) {
  const { box, icon, Icon } = TONES[tone];
  return (
    <div role={role} className={cx("flex gap-3 rounded-xl border px-4 py-3 text-sm animate-fade-in", box, className)}>
      <span className={cx("mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-lg [&_svg]:size-3.5", icon)}>
        <Icon />
      </span>
      <div className="min-w-0 flex-1 space-y-1">
        {title && <p className="font-bold">{title}</p>}
        {children && <div className="leading-7">{children}</div>}
        {actions && <div className="flex flex-wrap items-center gap-2 pt-1">{actions}</div>}
      </div>
    </div>
  );
}
