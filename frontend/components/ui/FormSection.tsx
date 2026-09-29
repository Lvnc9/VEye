import type { ReactNode } from "react";
import { cx } from "./cx";

/** One numbered part of a long form, inside a card: a step badge, a title with its line, and the
 *  fields. Sections stack with a hairline between them. */
export function FormSection({
  step,
  title,
  description,
  actions,
  className,
  children,
}: {
  step: number;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={cx("border-t border-slate-100 px-5 py-6 first:border-t-0 sm:px-6", className)}>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-50 text-xs font-bold text-brand-700 ring-1 ring-inset ring-brand-600/15 tabular-nums">
            {step.toLocaleString("fa-IR")}
          </span>
          <div>
            <h3 className="text-sm font-bold leading-7 text-slate-900">{title}</h3>
            {description && <p className="text-xs leading-6 text-slate-500">{description}</p>}
          </div>
        </div>
        {actions}
      </div>
      <div className="space-y-4">{children}</div>
    </section>
  );
}
