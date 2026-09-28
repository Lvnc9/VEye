"use client";

import type { ReactNode } from "react";
import { cx } from "./cx";

/**
 * A pill-shaped choice between a few options: the chosen one is a raised white chip. As `tabs` it is a
 * tab strip (aria-selected); otherwise a group of toggle buttons (aria-pressed).
 */
export function Segmented<T extends string>({
  items,
  value,
  onChange,
  label,
  tabs = false,
  size = "md",
  className,
}: {
  items: readonly (readonly [T, ReactNode])[];
  value: T;
  onChange: (value: T) => void;
  label: string;
  tabs?: boolean;
  size?: "sm" | "md";
  className?: string;
}) {
  return (
    <div
      role={tabs ? "tablist" : "group"}
      aria-label={label}
      className={cx("inline-flex rounded-lg bg-slate-100 p-1 ring-1 ring-inset ring-slate-200/70", className)}
    >
      {items.map(([id, text]) => {
        const on = id === value;
        return (
          <button
            key={id}
            type="button"
            role={tabs ? "tab" : undefined}
            aria-selected={tabs ? on : undefined}
            aria-pressed={tabs ? undefined : on}
            onClick={() => onChange(id)}
            className={cx(
              "flex-1 whitespace-nowrap rounded-md transition-[background-color,color,box-shadow] duration-200",
              size === "sm" ? "px-2.5 py-0.5 text-xs" : "px-3 py-1.5 text-sm",
              on ? "bg-white text-slate-900 shadow-sm ring-1 ring-slate-900/5" : "text-slate-500 hover:text-slate-800",
            )}
          >
            {text}
          </button>
        );
      })}
    </div>
  );
}
