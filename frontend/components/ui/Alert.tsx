import type { ReactNode } from "react";
import { CircleAlert, CircleCheck, Info, TriangleAlert } from "lucide-react";
import { cx } from "./cx";

type AlertTone = "info" | "success" | "warning" | "danger";

const TONES: Record<AlertTone, { box: string; icon: string; Icon: typeof Info }> = {
  info: { box: "border-brand-200 bg-brand-50/70 text-brand-900", icon: "text-brand-600", Icon: Info },
  success: { box: "border-emerald-200 bg-emerald-50/70 text-emerald-900", icon: "text-emerald-600", Icon: CircleCheck },
  warning: { box: "border-amber-200 bg-amber-50/80 text-amber-900", icon: "text-amber-600", Icon: TriangleAlert },
  danger: { box: "border-rose-200 bg-rose-50/80 text-rose-900", icon: "text-rose-600", Icon: CircleAlert },
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
      <Icon className={cx("mt-1 size-4", icon)} />
      <div className="min-w-0 flex-1 space-y-1">
        {title && <p className="font-bold">{title}</p>}
        {children && <div className="leading-7">{children}</div>}
        {actions && <div className="flex flex-wrap items-center gap-2 pt-1">{actions}</div>}
      </div>
    </div>
  );
}
