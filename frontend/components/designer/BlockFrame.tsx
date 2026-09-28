"use client";

import type { ReactNode } from "react";
import { SECTION_TYPE_LABELS, type SectionType } from "@/lib/types";
import { IconButton } from "./ui";
import { ChevronDown, ChevronUp, GripVertical, X } from "lucide-react";
import type { useDragReorder } from "./useDragReorder";

type Drag = ReturnType<typeof useDragReorder>;

/** The chrome around every block: its title and the ↑ ↓ ✕ controls V_1.0's
 *  DynamicItemFrame gave each one (utils.py:1103-1162), plus (Phase 12) a grip
 *  to drag the block to a new place. */
export function BlockFrame({
  type,
  index,
  total,
  disabled,
  onMove,
  onRemove,
  drag,
  dragKey,
  children,
}: {
  type: SectionType;
  index: number;
  total: number;
  disabled: boolean;
  onMove: (direction: -1 | 1) => void;
  onRemove: () => void;
  /** Drag-to-reorder for the list this block is in; `index` is 1-based. */
  drag?: Drag;
  dragKey?: string;
  children: ReactNode;
}) {
  const position = index - 1;
  const marker = drag?.marker(position);
  return (
    <section
      {...(drag ? drag.rowProps(position) : {})}
      className={`relative rounded-2xl border border-slate-200/80 bg-white shadow-card transition-[opacity,box-shadow,border-color] duration-200 focus-within:border-brand-300 focus-within:shadow-raised ${drag?.isDragging(position) ? "scale-[0.99] opacity-40" : ""}`}
    >
      {marker && (
        <span
          aria-hidden="true"
          className={`absolute inset-x-4 h-1 rounded-full bg-brand-500 shadow-[0_0_10px_rgb(14_165_233/0.6)] animate-fade-in ${marker === "before" ? "-top-2.5" : "-bottom-2.5"}`}
        />
      )}
      <header className="flex items-center justify-between gap-2 border-b border-slate-100 px-3 py-2 sm:px-4">
        <h3 className="flex items-center gap-2 text-sm font-bold text-slate-800">
          {drag && !disabled && (
            <span
              {...drag.gripProps(position, dragKey ?? String(index))}
              className="flex size-8 cursor-grab select-none items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700 active:cursor-grabbing"
            >
              <GripVertical className="size-4" />
            </span>
          )}
          <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-brand-50 px-1.5 text-xs font-bold text-brand-700 ring-1 ring-inset ring-brand-600/15 tabular-nums">
            {index}
          </span>
          {SECTION_TYPE_LABELS[type]}
        </h3>
        {!disabled && (
          <div className="flex items-center gap-0.5">
            <IconButton label="انتقال به بالا" onClick={() => onMove(-1)} disabled={index === 1}>
              <ChevronUp />
            </IconButton>
            <IconButton label="انتقال به پایین" onClick={() => onMove(1)} disabled={index === total}>
              <ChevronDown />
            </IconButton>
            <IconButton label="حذف بخش" onClick={onRemove} tone="danger">
              <X />
            </IconButton>
          </div>
        )}
      </header>
      <div className="p-4 sm:p-5">{children}</div>
    </section>
  );
}
