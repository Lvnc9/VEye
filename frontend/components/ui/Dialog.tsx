"use client";

import { useRef, useState, type ReactNode } from "react";
import { X } from "lucide-react";
import { Dialog as D } from "radix-ui";
import { IconButton } from "./IconButton";
import { cx } from "./cx";

const SIZES = { sm: "sm:max-w-md", md: "sm:max-w-lg", lg: "sm:max-w-xl", xl: "sm:max-w-2xl" } as const;

/**
 * A modal window (Radix Dialog): the page dims and softens behind it, and the panel rises in — a bottom
 * sheet on a phone, near the top on a larger screen. Escape and a click outside close it unless `busy`.
 * Focus goes inside (to whatever the content focused itself, else the panel), Tab stays inside, the page
 * behind is hidden from screen readers and doesn't scroll, and focus returns to the opener when it closes.
 *
 * Callers mount it only while it is open (there is no `open` prop) and unmount it in `onClose`, so it has
 * no exit animation. It is drawn into `document.body`, so no transformed ancestor can trap it.
 */
export function Dialog({
  label,
  title,
  description,
  onClose,
  busy = false,
  size = "md",
  showClose = true,
  className,
  children,
}: {
  /** The accessible name; defaults to `title` when that is text. */
  label: string;
  title?: ReactNode;
  description?: ReactNode;
  onClose: () => void;
  /** While true, the dialog can't be dismissed (a request is in flight). */
  busy?: boolean;
  size?: keyof typeof SIZES;
  showClose?: boolean;
  className?: string;
  children: ReactNode;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  // Who had focus before the dialog opened — read during the first render, before any child focuses.
  // Radix would send focus back to a <Dialog.Trigger>; callers open dialogs from their own buttons.
  const [opener] = useState<Element | null>(() => (typeof document === "undefined" ? null : document.activeElement));
  const dismiss = (event: React.MouseEvent) => {
    if (event.target === event.currentTarget && !busy) onClose();
  };
  return (
    <D.Root open onOpenChange={(open) => !open && !busy && onClose()}>
      <D.Portal>
        <D.Overlay className="fixed inset-0 z-50 bg-slate-950/50 backdrop-blur-[3px] animate-fade-in" />
        {/* The content is the whole scrolling layer, not just the panel: a date picker or a long form can
            reach past the panel's edge and the layer scrolls, as a page would. A click on the bare layer
            closes the dialog. */}
        <D.Content
          aria-label={label}
          aria-describedby={undefined}
          onEscapeKeyDown={(event) => busy && event.preventDefault()}
          onOpenAutoFocus={(event) => {
            // Radix asks only when the content took no focus itself (an autoFocus field keeps it): then
            // focus the panel, not the first button (the close «×»).
            event.preventDefault();
            panelRef.current?.focus();
          }}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            if (opener instanceof HTMLElement && opener.isConnected) opener.focus();
          }}
          onClick={dismiss}
          className="fixed inset-0 z-50 overflow-y-auto overscroll-contain outline-none"
        >
          <div className="flex min-h-full items-end justify-center sm:items-start sm:p-4 sm:pt-[10vh]" onClick={dismiss}>
            <div
              ref={panelRef}
              tabIndex={-1}
              className={cx(
                "veye-dialog relative w-full rounded-t-3xl border border-border bg-popover p-5 text-popover-foreground shadow-overlay outline-none",
                "pb-[max(1.25rem,env(safe-area-inset-bottom))] sm:rounded-2xl sm:p-6",
                SIZES[size],
                className,
              )}
            >
              {/* A grab handle: this is a sheet on a phone. */}
              <span aria-hidden className="mx-auto -mt-2 mb-3 block h-1 w-10 rounded-full bg-border sm:hidden" />
              <span
                aria-hidden
                className="pointer-events-none absolute inset-x-8 top-0 h-px bg-gradient-to-l from-transparent via-primary/50 to-transparent"
              />
              {/* Radix wants a title for screen readers; `label` is it when nothing is shown. */}
              {!title && <D.Title className="sr-only">{label}</D.Title>}
              {(title || showClose) && (
                <div className="mb-4 flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    {title && <D.Title className="text-lg font-bold leading-8 text-foreground">{title}</D.Title>}
                    {description && <D.Description className="mt-0.5 text-sm text-muted-foreground">{description}</D.Description>}
                  </div>
                  {showClose && (
                    <IconButton label="بستن" size="sm" onClick={onClose} disabled={busy} className="-me-2 -mt-1">
                      <X />
                    </IconButton>
                  )}
                </div>
              )}
              <div className="space-y-4">{children}</div>
            </div>
          </div>
        </D.Content>
      </D.Portal>
    </D.Root>
  );
}

/** The dialog's buttons, at the end of the row (the left, in RTL), wrapping on a phone. */
export function DialogFooter({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx("flex flex-wrap-reverse justify-end gap-2 pt-2", className)}>{children}</div>;
}
