"use client";

import { useId, type ReactNode } from "react";
import { LayoutGroup, m } from "motion/react";
import { cx } from "./cx";

const GLIDE = { type: "spring", stiffness: 460, damping: 38, mass: 0.7 } as const;

/**
 * A pill-shaped choice between a few options: a raised chip glides under the chosen one (after 21st.dev's
 * «Capsule Tabs» / «Slide Tabs»). As `tabs` it is a tab strip (aria-selected); otherwise a group of toggle
 * buttons (aria-pressed).
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
  const groupId = useId();
  return (
    <LayoutGroup id={groupId}>
      <div
        role={tabs ? "tablist" : "group"}
        aria-label={label}
        className={cx("inline-flex rounded-xl bg-muted p-1 ring-1 ring-inset ring-border", className)}
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
                "relative flex-1 whitespace-nowrap rounded-lg transition-colors duration-200",
                size === "sm" ? "px-2.5 py-0.5 text-xs pointer-coarse:py-2" : "px-3 py-1.5 text-sm pointer-coarse:py-2.5",
                on ? "font-bold text-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {on && (
                <m.span
                  layoutId="segment-chip"
                  transition={GLIDE}
                  aria-hidden
                  className="absolute inset-0 rounded-lg bg-card shadow-sm ring-1 ring-foreground/5 dark:bg-white/10"
                />
              )}
              <span className="relative">{text}</span>
            </button>
          );
        })}
      </div>
    </LayoutGroup>
  );
}
