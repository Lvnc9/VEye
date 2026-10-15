"use client";

import { useCallback, useSyncExternalStore } from "react";
import { SIDEBAR_STORAGE_KEY } from "@/lib/theme";
import { parseSidebarState, type SidebarState } from "@/lib/nav";

/**
 * The desktop sidebar's rail state. It lives on <html data-sidebar> — set before the first paint by the
 * theme script, so a collapsed rail never jumps open on load — and the layout reads it with CSS only (the
 * `rail:` variant). React reads it here just for what CSS can't do (tooltips, the toggle's label).
 */
function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-sidebar"] });
  return () => observer.disconnect();
}

const read = (): SidebarState => parseSidebarState(document.documentElement.getAttribute("data-sidebar"));

export function useSidebarState(): [SidebarState, () => void] {
  const state = useSyncExternalStore(subscribe, read, () => "expanded" as const);
  const toggle = useCallback(() => {
    const next: SidebarState = read() === "collapsed" ? "expanded" : "collapsed";
    if (next === "collapsed") document.documentElement.setAttribute("data-sidebar", "collapsed");
    else document.documentElement.removeAttribute("data-sidebar");
    try {
      localStorage.setItem(SIDEBAR_STORAGE_KEY, next);
    } catch {
      /* storage blocked: the rail stays as chosen until the page reloads */
    }
  }, []);
  return [state, toggle];
}
