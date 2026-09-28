import type { HTMLAttributes, ReactNode } from "react";
import { cx } from "./cx";

export const cardClass = "rounded-2xl border border-slate-200/80 bg-white shadow-card";

interface CardProps extends HTMLAttributes<HTMLElement> {
  as?: "section" | "div" | "article" | "aside" | "header";
  /** No inner padding — for tables and lists that run edge to edge. */
  flush?: boolean;
}

/** The white surface every block of a page sits on. */
export function Card({ as: Tag = "section", flush = false, className, children, ...rest }: CardProps) {
  return (
    <Tag className={cx(cardClass, !flush && "p-5 sm:p-6", className)} {...rest}>
      {children}
    </Tag>
  );
}

/** A card's title row: an optional icon tile, the title and a line under it, and actions at the end. */
export function CardHeader({
  title,
  description,
  icon,
  actions,
  className,
  id,
}: {
  title: ReactNode;
  description?: ReactNode;
  icon?: ReactNode;
  actions?: ReactNode;
  className?: string;
  /** For `aria-labelledby` on the card. */
  id?: string;
}) {
  return (
    <div className={cx("mb-4 flex flex-wrap items-start justify-between gap-3", className)}>
      <div className="flex min-w-0 items-start gap-3">
        {icon && (
          <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700 ring-1 ring-brand-600/10 [&_svg]:size-[18px]">
            {icon}
          </span>
        )}
        <div className="min-w-0">
          <h2 id={id} className="text-base font-bold text-slate-900">
            {title}
          </h2>
          {description && <p className="mt-0.5 text-sm text-slate-500">{description}</p>}
        </div>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
