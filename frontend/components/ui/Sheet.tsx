"use client";

import type { ReactNode } from "react";
import { Dialog as D } from "radix-ui";
import { cx } from "./cx";

/**
 * A panel that slides in from a screen edge over a dimmed page (Radix Dialog): focus stays inside,
 * Escape and a tap outside close it, and it slides back out (it stays mounted while `open` turns false,
 * so the exit animation plays). `side` is physical: "right" is the start edge in RTL.
 */
export function Sheet({
  open,
  onOpenChange,
  label,
  side = "right",
  className,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  label: string;
  side?: "right" | "left" | "bottom";
  className?: string;
  children: ReactNode;
}) {
  return (
    <D.Root open={open} onOpenChange={onOpenChange}>
      <D.Portal>
        <D.Overlay
          className={cx(
            "fixed inset-0 z-50 bg-slate-950/50 backdrop-blur-[2px]",
            "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0",
          )}
        />
        <D.Content
          aria-describedby={undefined}
          className={cx(
            "fixed z-50 flex flex-col outline-none shadow-overlay",
            "data-[state=open]:animate-in data-[state=open]:duration-300 data-[state=open]:ease-out-quint",
            "data-[state=closed]:animate-out data-[state=closed]:duration-200 data-[state=closed]:ease-in-quart",
            side === "right" && "inset-y-0 right-0 w-80 max-w-[85vw] data-[state=open]:slide-in-from-right data-[state=closed]:slide-out-to-right",
            side === "left" && "inset-y-0 left-0 w-80 max-w-[85vw] data-[state=open]:slide-in-from-left data-[state=closed]:slide-out-to-left",
            side === "bottom" &&
              "inset-x-0 bottom-0 max-h-[90dvh] rounded-t-3xl data-[state=open]:slide-in-from-bottom data-[state=closed]:slide-out-to-bottom",
            className,
          )}
        >
          <D.Title className="sr-only">{label}</D.Title>
          {children}
        </D.Content>
      </D.Portal>
    </D.Root>
  );
}

/** Closes the sheet it sits in — wrap a link with it so following the link also closes the sheet. */
export const SheetClose = D.Close;
