import type { ReactNode } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { buttonClass } from "@/components/ui/Button";
import { cx } from "@/components/ui/cx";

/**
 * A full-width notice for «page not found» and «something broke»: a large soft numeral behind an icon
 * tile, what happened in plain Persian, and the way out (after 21st.dev's «404 Error Page With Actions»).
 * Follows the theme; used inside the app's frame (the signed-in shell stays) and on its own.
 */
export function ErrorScreen({
  code,
  icon,
  title,
  message,
  actions,
  fullPage = false,
}: {
  /** The big numeral behind the icon, e.g. «۴۰۴». */
  code?: string;
  icon: ReactNode;
  title: string;
  message: string;
  actions?: ReactNode;
  /** Centred in the whole window (public pages) instead of in the shell's content area. */
  fullPage?: boolean;
}) {
  return (
    <div className={cx("relative isolate flex items-center justify-center px-4 text-center", fullPage ? "min-h-dvh" : "min-h-[60dvh]")}>
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(40%_50%_at_50%_45%,color-mix(in_oklch,var(--primary)_10%,transparent),transparent)]"
      />
      <div className="max-w-md">
        <div className="relative mx-auto mb-6 flex size-28 items-center justify-center">
          {code && (
            <span aria-hidden className="absolute -top-6 text-[7rem] font-black leading-none text-foreground/[0.05] select-none">
              {code}
            </span>
          )}
          <span className="relative flex size-16 items-center justify-center rounded-2xl bg-card text-primary shadow-raised ring-1 ring-border [&_svg]:size-8">
            {icon}
          </span>
        </div>
        <h1 className="text-2xl font-black text-foreground">{title}</h1>
        <p className="mt-2 text-sm leading-7 text-muted-foreground">{message}</p>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
          {actions}
          <Link href="/dashboard" className={buttonClass({ variant: actions ? "secondary" : "primary" })}>
            <ArrowRight />
            بازگشت به داشبورد
          </Link>
        </div>
      </div>
    </div>
  );
}
