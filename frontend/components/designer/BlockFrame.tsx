"use client";

import type { ReactNode } from "react";
import { SECTION_TYPE_LABELS, type SectionType } from "@/lib/types";
import { IconButton } from "./ui";
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
      className={`relative rounded-lg border border-slate-200 bg-white shadow-sm ${drag?.isDragging(position) ? "opacity-40" : ""}`}
    >
      {marker && (
        <span
          aria-hidden="true"
          className={`absolute inset-x-0 h-1 rounded bg-indigo-500 ${marker === "before" ? "-top-2.5" : "-bottom-2.5"}`}
        />
      )}
      <header className="flex items-center justify-between border-b border-slate-100 px-4 py-2">
        <h3 className="flex items-center text-sm font-semibold text-slate-800">
          {drag && !disabled && (
            <span
              {...drag.gripProps(position, dragKey ?? String(index))}
              className="me-1 cursor-grab select-none px-1 text-lg leading-none text-slate-400 hover:text-slate-700 active:cursor-grabbing"
            >
              ⠿
            </span>
          )}
          <span className="ms-1 inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-slate-100 px-1.5 text-xs text-slate-600">
            {index}
          </span>
          {SECTION_TYPE_LABELS[type]}
        </h3>
        {!disabled && (
          <div className="flex items-center">
            <IconButton label="انتقال به بالا" onClick={() => onMove(-1)} disabled={index === 1}>
              ↑
            </IconButton>
            <IconButton label="انتقال به پایین" onClick={() => onMove(1)} disabled={index === total}>
              ↓
            </IconButton>
            <IconButton label="حذف بخش" onClick={onRemove} tone="danger">
              ✕
            </IconButton>
          </div>
        )}
      </header>
      <div className="p-4">{children}</div>
    </section>
  );
}
