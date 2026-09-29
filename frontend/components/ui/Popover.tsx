"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { cx } from "./cx";

/**
 * A small panel that opens under its trigger button: a colour palette, a menu. It closes on a click
 * outside, on Escape (focus goes back to the trigger) and when `children` calls the `close` it is given.
 * The trigger carries the button's own look through `triggerClassName`.
 */
export function Popover({
  label,
  trigger,
  triggerClassName,
  disabled,
  pressed,
  panelClassName,
  children,
}: {
  /** The accessible name of the trigger (also its tooltip). */
  label: string;
  trigger: ReactNode;
  triggerClassName?: string;
  disabled?: boolean;
  pressed?: boolean;
  panelClassName?: string;
  children: (close: () => void) => ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLSpanElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelId = useId();

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <span ref={rootRef} className="relative inline-flex">
      <button
        ref={triggerRef}
        type="button"
        aria-label={label}
        title={label}
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        aria-pressed={pressed}
        disabled={disabled}
        // Keep the editor's selection: a button that takes focus would collapse it.
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => setOpen((value) => !value)}
        className={triggerClassName}
      >
        {trigger}
      </button>
      {open && (
        <div
          id={panelId}
          role="group"
          aria-label={label}
          className={cx(
            "absolute start-0 top-full z-30 mt-1.5 min-w-40 rounded-xl border border-slate-200 bg-white p-2 shadow-overlay animate-scale-in",
            panelClassName,
          )}
        >
          {children(() => setOpen(false))}
        </div>
      )}
    </span>
  );
}
