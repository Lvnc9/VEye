import type { ReactNode } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { cx } from "./cx";

/** The top of every screen: an optional way back, the title and its line, and the screen's main actions. */
export function PageHeader({
  title,
  subtitle,
  actions,
  back,
  className,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  back?: { href: string; label: string };
  className?: string;
}) {
  return (
    <header className={cx("flex flex-wrap items-end justify-between gap-x-4 gap-y-3", className)}>
      <div className="min-w-0">
        {back && (
          <Link
            href={back.href}
            className="group mb-2 inline-flex items-center gap-1.5 text-sm text-slate-500 transition-colors hover:text-slate-900"
          >
            <ArrowRight className="size-4 transition-transform duration-200 group-hover:translate-x-0.5" />
            {back.label}
          </Link>
        )}
        <h1 className="text-2xl font-bold leading-10 text-slate-900">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}
