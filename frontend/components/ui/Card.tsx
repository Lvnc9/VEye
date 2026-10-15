import type { HTMLAttributes, ReactNode } from "react";
import { cx } from "./cx";

export const cardClass = "rounded-2xl border border-border bg-card text-card-foreground shadow-card";

const VARIANTS = {
  default: "",
  /** Lifts on hover — for a card that is itself a link or a button. */
  interactive:
    "transition-[box-shadow,border-color,translate] duration-200 ease-out-quint hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-raised dark:hover:border-white/15",
  /** A hairline of brand gradient around the card — for the one thing on a page that should catch the eye. */
  gradient:
    "border-transparent [background:linear-gradient(var(--card),var(--card))_padding-box,linear-gradient(135deg,color-mix(in_oklch,var(--primary)_55%,transparent),color-mix(in_oklch,var(--color-indigo-400)_35%,transparent)_45%,var(--border)_80%)_border-box]",
} as const;

export type CardVariant = keyof typeof VARIANTS;

interface CardProps extends HTMLAttributes<HTMLElement> {
  as?: "section" | "div" | "article" | "aside" | "header";
  /** No inner padding — for tables and lists that run edge to edge. */
  flush?: boolean;
  variant?: CardVariant;
}

/** The surface every block of a page sits on. */
export function Card({ as: Tag = "section", flush = false, variant = "default", className, children, ...rest }: CardProps) {
  return (
    <Tag className={cx(cardClass, VARIANTS[variant], !flush && "p-5 sm:p-6", className)} {...rest}>
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
        {icon && <IconTile>{icon}</IconTile>}
        <div className="min-w-0">
          <h2 id={id} className="text-base font-bold text-foreground">
            {title}
          </h2>
          {description && <p className="mt-0.5 text-sm text-muted-foreground">{description}</p>}
        </div>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/** The small rounded tile an icon sits in at the head of a card or a stat. */
export function IconTile({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cx(
        "flex size-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-b from-primary/15 to-primary/5 text-primary",
        "ring-1 ring-inset ring-primary/15 [&_svg]:size-[18px]",
        className,
      )}
    >
      {children}
    </span>
  );
}
