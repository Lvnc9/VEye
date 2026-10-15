"use client";

import { useId, useRef, type KeyboardEvent, type ReactNode } from "react";
import { LayoutGroup, m } from "motion/react";
import { cx } from "./cx";

export interface TabItem<T extends string> {
  id: T;
  label: ReactNode;
  /** A badge or count shown after the label. */
  extra?: ReactNode;
}

const GLIDE = { type: "spring", stiffness: 420, damping: 36, mass: 0.8 } as const;

/**
 * An underlined tab strip whose indicator glides to the selected tab (a motion layout animation, scoped
 * to this strip so two strips on one page never trade indicators). Arrow keys move the selection in
 * reading order: ← goes forward in a right-to-left page.
 */
export function Tabs<T extends string>({
  items,
  value,
  onChange,
  label,
  className,
}: {
  items: TabItem<T>[];
  value: T;
  onChange: (id: T) => void;
  label: string;
  className?: string;
}) {
  const listRef = useRef<HTMLDivElement>(null);
  const groupId = useId();

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const index = items.findIndex((item) => item.id === value);
    let next = index;
    if (event.key === "ArrowLeft") next = (index + 1) % items.length;
    else if (event.key === "ArrowRight") next = (index - 1 + items.length) % items.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = items.length - 1;
    else return;
    event.preventDefault();
    onChange(items[next].id);
    listRef.current?.querySelectorAll<HTMLElement>('[role="tab"]')[next]?.focus();
  }

  return (
    <LayoutGroup id={groupId}>
      <div
        ref={listRef}
        role="tablist"
        aria-label={label}
        onKeyDown={onKeyDown}
        className={cx("relative flex gap-1 overflow-x-auto border-b border-border [scrollbar-width:none]", className)}
      >
        {items.map((item) => {
          const selected = item.id === value;
          return (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={selected}
              tabIndex={selected ? 0 : -1}
              onClick={() => onChange(item.id)}
              className={cx(
                "group relative flex h-11 shrink-0 items-center gap-2 px-3.5 text-sm transition-colors duration-150",
                selected ? "font-bold text-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              <span
                aria-hidden
                className="absolute inset-x-1 inset-y-1.5 rounded-lg bg-accent opacity-0 transition-opacity duration-150 group-hover:opacity-100"
              />
              <span className="relative flex items-center gap-2">
                {item.label}
                {item.extra}
              </span>
              {selected && (
                <m.span
                  layoutId="tab-indicator"
                  transition={GLIDE}
                  aria-hidden
                  className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-primary shadow-[0_0_10px_var(--primary)]"
                />
              )}
            </button>
          );
        })}
      </div>
    </LayoutGroup>
  );
}
