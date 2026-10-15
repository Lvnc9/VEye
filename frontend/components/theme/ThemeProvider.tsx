"use client";

import { createContext, useCallback, useContext, useLayoutEffect, useMemo, useSyncExternalStore } from "react";
import {
  THEME_STORAGE_KEY,
  applyTheme,
  parseThemeChoice,
  resolveTheme,
  type ResolvedTheme,
  type ThemeChoice,
} from "@/lib/theme";

interface ThemeContextValue {
  choice: ThemeChoice;
  resolved: ResolvedTheme;
  setChoice: (choice: ThemeChoice) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

const DARK_QUERY = "(prefers-color-scheme: dark)";
const CHANGE_EVENT = "veye-theme-change";

function subscribe(onChange: () => void) {
  const media = window.matchMedia(DARK_QUERY);
  media.addEventListener("change", onChange);
  window.addEventListener("storage", onChange); // another tab changed it
  window.addEventListener(CHANGE_EVENT, onChange); // this tab changed it
  return () => {
    media.removeEventListener("change", onChange);
    window.removeEventListener("storage", onChange);
    window.removeEventListener(CHANGE_EVENT, onChange);
  };
}

function readChoice(): ThemeChoice {
  try {
    return parseThemeChoice(localStorage.getItem(THEME_STORAGE_KEY));
  } catch {
    return parseThemeChoice(null);
  }
}

/**
 * The theme as React state. The DOM was already set before paint by THEME_INIT_SCRIPT; this keeps it in
 * step afterwards (the switch, another tab, the system turning dark at night) and re-applies it after
 * React's development remount, which resets <html>'s attributes (Next 16 docs). The server renders the
 * light default: nothing theme-dependent may be decided in markup — use `dark:` classes instead.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const choice = useSyncExternalStore(subscribe, readChoice, () => parseThemeChoice(null));
  const systemDark = useSyncExternalStore(
    subscribe,
    () => window.matchMedia(DARK_QUERY).matches,
    () => false,
  );
  const resolved = resolveTheme(choice, systemDark);

  useLayoutEffect(() => {
    applyTheme(document.documentElement, resolved);
  }, [resolved]);

  const setChoice = useCallback((next: ThemeChoice) => {
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      /* storage blocked: the choice lasts until the page reloads */
    }
    window.dispatchEvent(new Event(CHANGE_EVENT));
  }, []);

  const value = useMemo(() => ({ choice, resolved, setChoice }), [choice, resolved, setChoice]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const value = useContext(ThemeContext);
  if (!value) throw new Error("useTheme must be used inside ThemeProvider");
  return value;
}
