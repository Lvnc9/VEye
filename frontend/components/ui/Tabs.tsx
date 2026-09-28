"use client";

import { useLayoutEffect, useRef, type KeyboardEvent, type ReactNode } from "react";
import { cx } from "./cx";

export interface TabItem<T extends string> {
  id: T;
  label: ReactNode;
  /** A badge or count shown after the label. */
  extra?: ReactNode;
}

/**
 * An underlined tab strip whose indicator glides to the selected tab. The indicator is positioned by
 * writing to its style (never React state), so measuring it never re-renders the strip. Arrow keys move
 * the selection in reading order: ← goes forward in a right-to-left page.
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
  const barRef = useRef<HTMLSpanElement>(null);
  const placed = useRef(false);

  useLayoutEffect(() => {
    const list = listRef.current;
    const bar = barRef.current;
    if (!list || !bar) return;
    const place = () => {
      const tab = list.querySelector<HTMLElement>('[aria-selected="true"]');
      if (!tab) return;
      bar.style.transform = `translateX(${tab.offsetLeft}px) scaleX(${tab.offsetWidth})`;
      if (!placed.current) {
        // The first placement jumps; later ones glide.
        placed.current = true;
        requestAnimationFrame(() => bar.classList.add("transition-transform"));
      }
    };
    place();
    const observer = new ResizeObserver(place);
    observer.observe(list);
    return () => observer.disconnect();
  }, [value, items.length]);

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
    <div
      ref={listRef}
      role="tablist"
      aria-label={label}
      onKeyDown={onKeyDown}
      className={cx("relative flex gap-1 overflow-x-auto border-b border-slate-200", className)}
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
              "relative flex h-11 shrink-0 items-center gap-2 rounded-t-lg px-3.5 text-sm transition-colors duration-150",
              selected ? "text-slate-900" : "text-slate-500 hover:bg-slate-100/70 hover:text-slate-800",
            )}
          >
            {item.label}
            {item.extra}
          </button>
        );
      })}
      <span
        ref={barRef}
        aria-hidden
        className="pointer-events-none absolute bottom-0 left-0 h-0.5 w-px origin-left rounded-full bg-brand-600 duration-300 ease-out-quint"
      />
    </div>
  );
}
