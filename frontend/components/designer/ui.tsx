"use client";

import type { ReactNode } from "react";
import { Plus } from "lucide-react";
import type { DesignerSection } from "@/lib/types";
import { controlClass } from "@/components/ui/Field";
import { IconButton as UiIconButton } from "@/components/ui/IconButton";

/** Designer text boxes and text areas: the shared control look, sized by their padding (they grow). */
export const inputClass = `${controlClass} w-full py-2`;

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
  return (
    <UiIconButton label={label} onClick={onClick} disabled={disabled} tone={tone} size="sm">
      {children}
    </UiIconButton>
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
      className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-dashed border-slate-300 px-3 text-sm text-slate-600 transition-[background-color,border-color,color,transform] duration-150 hover:border-brand-400 hover:bg-brand-50/60 hover:text-brand-800 active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-slate-300 disabled:hover:bg-transparent disabled:hover:text-slate-600"
    >
      <Plus className="size-4" />
      {children}
    </button>
  );
}

export function FieldLabel({ children }: { children: ReactNode }) {
  return <span className="mb-1.5 block text-sm text-slate-700">{children}</span>;
}
