"use client";

import { useRef, useState, type ReactNode } from "react";
import { Popover as P } from "radix-ui";
import { cx } from "./cx";

/**
 * A small panel that opens under its trigger button: a colour palette, a menu. It closes on a click
 * outside, on Escape (focus goes back to the trigger) and when `children` calls the `close` it is given.
 * The trigger carries the button's own look through `triggerClassName`. Drawn in a portal (Radix), so no
 * scrolling toolbar clips it; it flips to stay on screen.
 *
 * Built for the rich editor's toolbar: neither opening nor closing takes focus from the editor, so its
 * selection survives — except Escape, which returns focus to the trigger for keyboard users.
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
  const closedByEscape = useRef(false);

  return (
    <P.Root open={open} onOpenChange={setOpen}>
      <P.Trigger
        type="button"
        aria-label={label}
        title={label}
        aria-pressed={pressed}
        disabled={disabled}
        // Keep the editor's selection: a button that takes focus would collapse it.
        onMouseDown={(event) => event.preventDefault()}
        className={triggerClassName}
      >
        {trigger}
      </P.Trigger>
      <P.Portal>
        <P.Content
          role="group"
          aria-label={label}
          align="start"
          sideOffset={6}
          collisionPadding={8}
          onOpenAutoFocus={(event) => event.preventDefault()}
          onEscapeKeyDown={() => (closedByEscape.current = true)}
          onCloseAutoFocus={(event) => {
            if (!closedByEscape.current) event.preventDefault();
            closedByEscape.current = false;
          }}
          className={cx(
            "z-[60] min-w-40 rounded-xl border border-border bg-popover p-2 text-popover-foreground shadow-overlay",
            "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-1",
            "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95",
            panelClassName,
          )}
        >
          {children(() => setOpen(false))}
        </P.Content>
      </P.Portal>
    </P.Root>
  );
}
