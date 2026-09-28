"use client";

import { useState, type ReactNode } from "react";
import { Segmented } from "@/components/ui/Segmented";

/**
 * The editor beside its live paper (Phase 12): two columns from `xl`, the paper
 * sticky beside the editor; below that, «ویرایش | پیش‌نمایش» tabs. Both panes stay
 * mounted, so switching tabs keeps unsaved input and the drawn pages.
 */
export function PaperLayout({ editor, paper }: { editor: ReactNode; paper: ReactNode }) {
  const [tab, setTab] = useState<"editor" | "paper">("editor");
  return (
    <div className="space-y-4">
      <Segmented
        tabs
        label="نما"
        className="flex w-full xl:hidden"
        items={[
          ["editor", "ویرایش"],
          ["paper", "پیش‌نمایش"],
        ]}
        value={tab}
        onChange={setTab}
      />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,34rem)] xl:items-start">
        <div className={`min-w-0 space-y-6 ${tab === "editor" ? "" : "hidden xl:block"}`}>{editor}</div>
        <div className={`min-w-0 xl:sticky xl:top-4 ${tab === "paper" ? "" : "hidden xl:block"}`}>{paper}</div>
      </div>
    </div>
  );
}
