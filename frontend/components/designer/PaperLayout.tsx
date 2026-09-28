"use client";

import { useState, type ReactNode } from "react";

/**
 * The editor beside its live paper (Phase 12): two columns from `xl`, the paper
 * sticky beside the editor; below that, «ویرایش | پیش‌نمایش» tabs. Both panes stay
 * mounted, so switching tabs keeps unsaved input and the drawn pages.
 */
export function PaperLayout({ editor, paper }: { editor: ReactNode; paper: ReactNode }) {
  const [tab, setTab] = useState<"editor" | "paper">("editor");
  return (
    <div className="space-y-4">
      <div role="tablist" aria-label="نما" className="flex rounded-lg border border-slate-200 bg-white p-1 text-sm shadow-sm xl:hidden">
        {(
          [
            ["editor", "ویرایش"],
            ["paper", "پیش‌نمایش"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={tab === value}
            onClick={() => setTab(value)}
            className={`flex-1 rounded-md px-3 py-1.5 font-medium ${tab === value ? "bg-slate-800 text-white" : "text-slate-600 hover:bg-slate-50"}`}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,34rem)] xl:items-start">
        <div className={`min-w-0 space-y-6 ${tab === "editor" ? "" : "hidden xl:block"}`}>{editor}</div>
        <div className={`min-w-0 xl:sticky xl:top-4 ${tab === "paper" ? "" : "hidden xl:block"}`}>{paper}</div>
      </div>
    </div>
  );
}
