"use client";

import type { ReactNode } from "react";
import { SECTION_TYPE_LABELS, type SectionType } from "@/lib/types";
import { IconButton } from "./ui";

/** The chrome around every block: its title and the ↑ ↓ ✕ controls V_1.0's
 *  DynamicItemFrame gave each one (utils.py:1103-1162). */
export function BlockFrame({
  type,
  index,
  total,
  disabled,
  onMove,
  onRemove,
  children,
}: {
  type: SectionType;
  index: number;
  total: number;
  disabled: boolean;
  onMove: (direction: -1 | 1) => void;
  onRemove: () => void;
  children: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <header className="flex items-center justify-between border-b border-slate-100 px-4 py-2">
        <h3 className="text-sm font-semibold text-slate-800">
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
