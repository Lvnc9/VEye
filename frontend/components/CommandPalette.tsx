"use client";

import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { useRouter } from "next/navigation";
import { CornerDownLeft, Search } from "lucide-react";
import { apiGet } from "@/lib/api-client";
import {
  OPEN_SEARCH_EVENT,
  SEARCH_DEBOUNCE_MS,
  flattenResults,
  isPaletteShortcut,
  moveActive,
  searchable,
  type SearchResponse,
} from "@/lib/search";
import { Dialog } from "@/components/ui/Dialog";
import { Kbd } from "@/components/ui/Kbd";
import { Skeleton } from "@/components/ui/Skeleton";
import { cx } from "@/components/ui/cx";

/**
 * ⌘K / Ctrl+K (Phase 22): one search box over documents, projects, non-conformances, audits, risks,
 * announcements, people and the chart, each scoped as its own screen scopes it (`GET /search/`). Mounted
 * once in the app shell; the top bar's button fires `OPEN_SEARCH_EVENT`. Arrow keys move, Enter opens.
 */
export function CommandPalette() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (isPaletteShortcut(event)) {
        event.preventDefault();
        setOpen((value) => !value);
      }
    };
    const onOpen = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener(OPEN_SEARCH_EVENT, onOpen);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener(OPEN_SEARCH_EVENT, onOpen);
    };
  }, []);

  return open ? <PaletteDialog onClose={() => setOpen(false)} /> : null;
}

function PaletteDialog({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const listId = useId();
  const input = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");
  const [answer, setAnswer] = useState<{ query: string; response: SearchResponse | null; error: boolean } | null>(null);
  const [active, setActive] = useState(-1);

  const query = text.trim();
  const ready = searchable(query);

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      apiGet<SearchResponse>("/search/", { q: query })
        .then((response) => {
          if (cancelled) return;
          setAnswer({ query, response, error: false });
          setActive(-1);
        })
        .catch(() => !cancelled && setAnswer({ query, response: null, error: true }));
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query, ready]);

  // An answer is only shown for the text it was asked for.
  const current = ready && answer?.query === query ? answer : null;
  const flat = flattenResults(current?.response?.groups ?? []);
  const loading = ready && !current;

  const go = useCallback(
    (url: string) => {
      onClose();
      router.push(url);
    },
    [onClose, router],
  );

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setActive((index) => moveActive(index, event.key === "ArrowDown" ? 1 : -1, flat.length));
    } else if (event.key === "Enter" && flat.length > 0) {
      event.preventDefault();
      go(flat[active >= 0 ? active : 0].url);
    }
  }

  let shown = 0;
  return (
    <Dialog label="جست‌وجو در همه‌جا" onClose={onClose} showClose={false} size="xl" className="p-0">
      <div className="-m-1 flex items-center gap-2 border-b border-border px-3 pb-3">
        <Search aria-hidden className="size-5 shrink-0 text-muted-foreground" />
        <input
          ref={input}
          autoFocus
          role="combobox"
          aria-expanded={flat.length > 0}
          aria-controls={listId}
          aria-activedescendant={active >= 0 ? flat[active]?.key : undefined}
          aria-autocomplete="list"
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder="جست‌وجوی مستند، پروژه، عدم‌انطباق، ریسک، شخص…"
          className="h-10 w-full bg-transparent text-base text-foreground outline-none placeholder:text-muted-foreground"
        />
        <Kbd>Esc</Kbd>
      </div>

      <div id={listId} role="listbox" aria-label="نتایج جست‌وجو" className="max-h-[60vh] overflow-y-auto pt-2">
        {!ready ? (
          <p className="px-3 py-8 text-center text-sm text-muted-foreground">دست‌کم دو حرف بنویسید.</p>
        ) : loading ? (
          <div className="space-y-2 px-3 py-2">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-5/6" />
          </div>
        ) : current?.error ? (
          <p className="px-3 py-8 text-center text-sm text-destructive">جست‌وجو انجام نشد. دوباره تلاش کنید.</p>
        ) : flat.length === 0 ? (
          <p className="px-3 py-8 text-center text-sm text-muted-foreground">نتیجه‌ای پیدا نشد.</p>
        ) : (
          current?.response?.groups.map((group) => (
            <div key={group.type} role="group" aria-label={group.label} className="pb-2">
              <p className="px-3 pb-1 pt-2 text-[11px] font-bold text-muted-foreground">{group.label}</p>
              {group.items.map((item) => {
                const index = shown++;
                const isActive = index === active;
                return (
                  <div
                    key={flat[index].key}
                    id={flat[index].key}
                    role="option"
                    aria-selected={isActive}
                    onMouseMove={() => setActive(index)}
                    onClick={() => go(item.url)}
                    className={cx(
                      "flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors",
                      isActive ? "bg-accent text-foreground" : "text-soft-foreground",
                    )}
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium text-foreground">{item.title}</span>
                      {item.subtitle && <span className="block truncate text-xs text-muted-foreground">{item.subtitle}</span>}
                    </span>
                    {isActive && <CornerDownLeft aria-hidden className="rtl-flip size-4 shrink-0 text-muted-foreground" />}
                  </div>
                );
              })}
            </div>
          ))
        )}
      </div>
    </Dialog>
  );
}
