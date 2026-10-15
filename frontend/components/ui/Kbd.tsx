import type { ReactNode } from "react";
import { cx } from "./cx";

/** A key on the keyboard, as in «Esc» or «⌘K». Latin, left to right. */
export function Kbd({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <kbd
      dir="ltr"
      className={cx(
        "inline-flex h-5 min-w-5 items-center justify-center rounded-md border border-border border-b-2 bg-muted px-1.5",
        "font-sans text-[11px] font-medium text-muted-foreground",
        className,
      )}
    >
      {children}
    </kbd>
  );
}
