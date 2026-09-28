"use client";

import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { X } from "lucide-react";
import { IconButton } from "./IconButton";
import { cx } from "./cx";

const SIZES = { sm: "sm:max-w-md", md: "sm:max-w-lg", lg: "sm:max-w-xl", xl: "sm:max-w-2xl" } as const;

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * A modal window: the page dims and softens behind it, and the panel rises in — from the bottom edge on a
 * phone, near the top on a larger screen. Escape and a click on the backdrop close it unless `busy`.
 * Focus goes inside (to whatever the content focused itself, else the panel), Tab stays inside, and focus
 * returns to the opener when it closes.
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
  const [opener] = useState<Element | null>(() => (typeof document === "undefined" ? null : document.activeElement));

  useEffect(() => {
    const panel = panelRef.current;
    if (panel && !panel.contains(document.activeElement)) panel.focus();
    return () => {
      if (opener instanceof HTMLElement && opener.isConnected) opener.focus();
    };
  }, [opener]);

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.stopPropagation();
      if (!busy) onClose();
      return;
    }
    if (event.key !== "Tab" || !panelRef.current) return;
    const items = Array.from(panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
      (element) => element.offsetParent !== null,
    );
    if (items.length === 0) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <div className="fixed inset-0 z-50" onKeyDown={onKeyDown}>
      <div aria-hidden className="absolute inset-0 bg-slate-950/45 backdrop-blur-[3px] animate-fade-in" />
      <div
        className="absolute inset-0 overflow-y-auto overscroll-contain"
        onClick={(event) => event.target === event.currentTarget && !busy && onClose()}
      >
        <div
          className="flex min-h-full items-end justify-center sm:items-start sm:p-4 sm:pt-[10vh]"
          onClick={(event) => event.target === event.currentTarget && !busy && onClose()}
        >
          <div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-label={label}
            tabIndex={-1}
            className={cx(
              "relative w-full rounded-t-2xl bg-white p-5 shadow-overlay ring-1 ring-slate-900/5 outline-none animate-scale-in",
              "pb-[max(1.25rem,env(safe-area-inset-bottom))] sm:rounded-2xl sm:p-6",
              SIZES[size],
              className,
            )}
          >
            {(title || showClose) && (
              <div className="mb-4 flex items-start justify-between gap-3">
                <div className="min-w-0">
                  {title && <h2 className="text-lg font-bold leading-8 text-slate-900">{title}</h2>}
                  {description && <p className="mt-0.5 text-sm text-slate-500">{description}</p>}
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
      </div>
    </div>
  );
}

/** The dialog's buttons, at the end of the row (the left, in RTL), wrapping on a phone. */
export function DialogFooter({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx("flex flex-wrap-reverse justify-end gap-2 pt-2", className)}>{children}</div>;
}
