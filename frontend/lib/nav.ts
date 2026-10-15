/**
 * Which navigation entry is "here". The most specific matching entry wins, so /documents/history doesn't
 * also light up «ساخت مستند» (whose href is a prefix of it); the dashboard matches only itself.
 */
export function activeHref(hrefs: readonly string[], pathname: string): string | undefined {
  return hrefs
    .filter((href) => pathname === href || (href !== "/dashboard" && pathname.startsWith(href + "/")))
    .sort((a, b) => b.length - a.length)[0];
}

/**
 * Screens where the phone's bottom tab bar steps aside: the document designer (its own save bar sits at
 * the bottom) and an open conversation (the message box sits at the bottom).
 */
export function hidesBottomNav(pathname: string, search: URLSearchParams | null): boolean {
  if (/^\/documents\/[^/]+\/edit\/?$/.test(pathname)) return true;
  if (pathname === "/inbox" && search?.get("c")) return true;
  return false;
}

export type SidebarState = "expanded" | "collapsed";

export function parseSidebarState(value: string | null | undefined): SidebarState {
  return value === "collapsed" ? "collapsed" : "expanded";
}
