"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutGroup, m } from "motion/react";
import { Menu } from "lucide-react";
import { unreadBadge, type InboxSummary } from "@/lib/chat";
import { activeHref } from "@/lib/nav";
import { cx } from "@/components/ui/cx";
import { PHONE_TABS } from "./nav";

const GLIDE = { type: "spring", stiffness: 420, damping: 36 } as const;

/**
 * Below `md`: a frosted tab bar at the foot of the screen with the four most-used places and «منو» for
 * the rest. It is the shell's last flex row (not `fixed`), so the page above simply ends where it starts
 * and a page's own sticky bar still sits above it. It pads itself above the phone's home indicator.
 */
export function BottomNav({ inbox, onOpenMenu, menuOpen }: { inbox: InboxSummary | null; onOpenMenu: () => void; menuOpen: boolean }) {
  const pathname = usePathname();
  const current = activeHref(
    PHONE_TABS.map((tab) => tab.href),
    pathname.startsWith("/documents/history") ? "" : pathname,
  );
  const badge = unreadBadge(inbox?.total ?? 0);

  return (
    <nav
      aria-label="میان‌برها"
      className="shrink-0 border-t border-border bg-background/85 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl md:hidden"
    >
      <LayoutGroup id="bottom-nav">
        <ul className="grid grid-cols-5">
          {PHONE_TABS.map((tab) => {
            const Icon = tab.icon;
            const active = tab.href === current;
            return (
              <li key={tab.href}>
                <Link
                  href={tab.href}
                  aria-current={active ? "page" : undefined}
                  className={cx(
                    "relative flex h-16 flex-col items-center justify-center gap-1 text-[11px] transition-colors",
                    active ? "font-bold text-primary" : "text-muted-foreground",
                  )}
                >
                  <span className="relative flex h-7 w-12 items-center justify-center">
                    {active && (
                      <m.span layoutId="bottom-active" transition={GLIDE} aria-hidden className="absolute inset-0 rounded-full bg-primary/12" />
                    )}
                    <Icon className="relative size-5" />
                    {tab.href === "/inbox" && badge && (
                      <span className="absolute -top-1 end-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-bold leading-none text-white tabular-nums ring-2 ring-background">
                        {badge}
                      </span>
                    )}
                  </span>
                  {tab.label}
                </Link>
              </li>
            );
          })}
          <li>
            <button
              type="button"
              onClick={onOpenMenu}
              aria-expanded={menuOpen}
              className="flex h-16 w-full flex-col items-center justify-center gap-1 text-[11px] text-muted-foreground"
            >
              <span className="flex h-7 w-12 items-center justify-center">
                <Menu className="size-5" />
              </span>
              منو
            </button>
          </li>
        </ul>
      </LayoutGroup>
    </nav>
  );
}
