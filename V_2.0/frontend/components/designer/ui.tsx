"use client";

import type { ReactNode } from "react";
import type { DesignerSection } from "@/lib/types";

export const inputClass =
  "w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm focus:border-slate-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500";

/** Props every block editor receives. Blocks change themselves through a
 *  functional `update` rather than a value: uploads resolve asynchronously, and
 *  a handler holding a stale copy of the block would overwrite whatever the
 *  author typed in the meantime. */
export interface BlockProps<T extends DesignerSection> {
  section: T;
  /** 1-based position among all blocks; V_1.0 shows it as a numbering hint
   *  (utils.py update_dynamic_numbering, poster_01.py:1503-1553). */
  index: number;
  disabled: boolean;
  update: (updater: (section: T) => T) => void;
}

export function IconButton({
  label,
  onClick,
  disabled,
  children,
  tone = "neutral",
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  children: ReactNode;
  tone?: "neutral" | "danger";
}) {
  const color =
    tone === "danger"
      ? "text-red-600 hover:bg-red-50 disabled:hover:bg-transparent"
      : "text-slate-600 hover:bg-slate-100 disabled:hover:bg-transparent";
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      className={`inline-flex h-8 min-w-8 items-center justify-center rounded px-2 text-sm disabled:cursor-not-allowed disabled:opacity-30 ${color}`}
    >
      {children}
    </button>
  );
}

export function AddButton({
  onClick,
  disabled,
  children,
}: {
  onClick: () => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="rounded border border-dashed border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:border-slate-400 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
    >
      + {children}
    </button>
  );
}

export function FieldLabel({ children }: { children: ReactNode }) {
  return <span className="mb-1 block text-sm font-medium text-slate-700">{children}</span>;
}
