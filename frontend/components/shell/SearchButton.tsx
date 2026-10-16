"use client";

import { Search } from "lucide-react";
import { OPEN_SEARCH_EVENT } from "@/lib/search";
import { Kbd } from "@/components/ui/Kbd";
import { Tooltip } from "@/components/ui/Tooltip";
import { cx } from "@/components/ui/cx";

/** The top bar's way into the ⌘K palette (`components/CommandPalette.tsx`, mounted in the app shell). */
export function SearchButton({ onDark = false }: { onDark?: boolean }) {
  return (
    <Tooltip content="جست‌وجو در همه‌جا" side="bottom">
      <button
        type="button"
        aria-label="جست‌وجو (⌘K)"
        onClick={() => window.dispatchEvent(new Event(OPEN_SEARCH_EVENT))}
        className={cx(
          "flex h-10 items-center gap-2 rounded-xl px-3 text-sm transition-colors",
          onDark ? "text-slate-300 hover:bg-white/10 hover:text-white" : "text-muted-foreground hover:bg-accent hover:text-foreground",
        )}
      >
        <Search className="size-[18px]" />
        <span className={cx("hidden lg:inline", onDark && "lg:hidden")}>جست‌وجو</span>
        {!onDark && <Kbd className="hidden lg:inline-flex">⌘K</Kbd>}
      </button>
    </Tooltip>
  );
}
