"use client";

import type { ReactNode } from "react";
import { Tooltip as T } from "radix-ui";
import { cx } from "./cx";

/**
 * A short label that appears beside its trigger on hover or keyboard focus (never on touch — say it
 * elsewhere too). `side` is physical: "left" in RTL is the reading direction's end. The trigger must be
 * one element that can take a ref (a button, a link).
 */
export function Tooltip({
  content,
  side = "top",
  align = "center",
  disabled = false,
  children,
}: {
  content: ReactNode;
  side?: "top" | "bottom" | "left" | "right";
  align?: "start" | "center" | "end";
  disabled?: boolean;
  children: ReactNode;
}) {
  if (disabled) return <>{children}</>;
  return (
    <T.Root>
      <T.Trigger asChild>{children}</T.Trigger>
      <T.Portal>
        <T.Content
          side={side}
          align={align}
          sideOffset={6}
          collisionPadding={8}
          className={cx(
            "z-[70] max-w-64 rounded-lg bg-slate-900 px-2.5 py-1.5 text-xs leading-5 text-slate-50 shadow-raised",
            "dark:bg-slate-100 dark:text-slate-900",
            "data-[state=delayed-open]:animate-in data-[state=delayed-open]:fade-in-0 data-[state=delayed-open]:zoom-in-95",
            "data-[state=instant-open]:animate-in data-[state=instant-open]:fade-in-0",
            "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95",
          )}
        >
          {content}
        </T.Content>
      </T.Portal>
    </T.Root>
  );
}
