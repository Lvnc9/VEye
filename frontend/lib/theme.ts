/**
 * Light / dark / system (UI 2, owner's decision 2026-10-15: light by default). The choice lives in
 * localStorage and is applied as a class on <html> by an inline script in <head>, before the first paint,
 * so a dark page never flashes white (Next 16 docs, preventing-flash-before-hydration.md §Themes).
 * The same script restores the collapsed sidebar rail, for the same reason.
 */

export type ThemeChoice = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export const THEME_STORAGE_KEY = "veye.theme";
export const SIDEBAR_STORAGE_KEY = "veye.sidebar";
export const DEFAULT_THEME: ThemeChoice = "light";

export const THEME_LABELS: Record<ThemeChoice, string> = {
  light: "روشن",
  dark: "تیره",
  system: "مطابق سیستم",
};

export function parseThemeChoice(value: string | null | undefined): ThemeChoice {
  return value === "light" || value === "dark" || value === "system" ? value : DEFAULT_THEME;
}

export function resolveTheme(choice: ThemeChoice, systemPrefersDark: boolean): ResolvedTheme {
  if (choice === "system") return systemPrefersDark ? "dark" : "light";
  return choice;
}

/** Puts the resolved theme on <html>: the `dark` class (Tailwind's variant) and `color-scheme`. */
export function applyTheme(root: HTMLElement, theme: ResolvedTheme): void {
  root.classList.toggle("dark", theme === "dark");
  root.style.colorScheme = theme;
}

/**
 * The inline <head> script: the same rules as parseThemeChoice + resolveTheme + applyTheme, in plain
 * ES5 because it runs before any bundle. Any failure (storage blocked) leaves the light default.
 */
export const THEME_INIT_SCRIPT =
  "(function(){try{var d=document.documentElement;" +
  `var t=localStorage.getItem(${JSON.stringify(THEME_STORAGE_KEY)});` +
  `if(t!=="light"&&t!=="dark"&&t!=="system")t=${JSON.stringify(DEFAULT_THEME)};` +
  'var dark=t==="dark"||(t==="system"&&window.matchMedia("(prefers-color-scheme: dark)").matches);' +
  'd.classList.toggle("dark",dark);d.style.colorScheme=dark?"dark":"light";' +
  `if(localStorage.getItem(${JSON.stringify(SIDEBAR_STORAGE_KEY)})==="collapsed")d.setAttribute("data-sidebar","collapsed");` +
  "}catch(e){}})();";
