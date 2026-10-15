"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, ChevronLeft, Menu } from "lucide-react";
import { unreadBadge, type InboxSummary } from "@/lib/chat";
import { useCurrentUser } from "@/lib/current-user";
import { activeHref } from "@/lib/nav";
import { BrandMark } from "@/components/ui/BrandMark";
import { Tooltip } from "@/components/ui/Tooltip";
import { cx } from "@/components/ui/cx";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { navItemsFor } from "./nav";
import { UserMenu } from "./UserMenu";

/** The bell: a link to the «اعلان‌ها» tab of the کارتابل, with the number of unread notices. */
function Bell_({ inbox, onDark }: { inbox: InboxSummary | null; onDark?: boolean }) {
  const count = inbox?.unread_notifications ?? 0;
  const badge = unreadBadge(count);
  const label = count > 0 ? `اعلان‌ها — ${count.toLocaleString("fa-IR")} خوانده‌نشده` : "اعلان‌ها";
  return (
    <Tooltip content="اعلان‌ها" side="bottom">
      <Link
        href="/inbox?tab=notifications"
        aria-label={label}
        className={cx(
          "relative flex size-10 items-center justify-center rounded-xl transition-colors",
          onDark ? "text-slate-300 hover:bg-white/10 hover:text-white" : "text-muted-foreground hover:bg-accent hover:text-foreground",
        )}
      >
        <Bell className="size-[18px]" />
        {badge && (
          <span
            aria-hidden
            className={cx(
              "absolute top-1.5 end-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-bold leading-none text-white tabular-nums",
              onDark ? "ring-2 ring-navy" : "ring-2 ring-background",
            )}
          >
            {badge}
          </span>
        )}
      </Link>
    </Tooltip>
  );
}

/**
 * The bar above the page. From `md` up: where you are (the menu group › the screen) and the bell, on a
 * frosted strip, with the theme switch. On a phone: the navy brand bar with the bell and your avatar menu — and the menu button
 * when the bottom tab bar has stepped aside (the designer, an open conversation).
 */
export function TopBar({
  inbox,
  onOpenMenu,
  menuOpen,
  showMenuButton,
}: {
  inbox: InboxSummary | null;
  onOpenMenu: () => void;
  menuOpen: boolean;
  showMenuButton: boolean;
}) {
  const pathname = usePathname();
  const { user } = useCurrentUser();
  const items = navItemsFor(user);
  const current = items.find((item) => item.href === activeHref(items.map((i) => i.href), pathname));

  return (
    <>
      <header className="hidden h-14 shrink-0 items-center justify-between gap-4 border-b border-border bg-background/80 px-6 backdrop-blur-xl md:flex lg:px-8">
        <nav aria-label="مسیر" className="flex min-w-0 items-center gap-1.5 text-sm">
          {current ? (
            <>
              <span className="truncate text-muted-foreground">{current.group}</span>
              <ChevronLeft aria-hidden className="size-3.5 shrink-0 text-subtle-foreground" />
              <Link href={current.href} className="truncate font-bold text-foreground hover:text-primary">
                {current.label}
              </Link>
            </>
          ) : (
            <span className="font-bold text-foreground">وی‌آی</span>
          )}
        </nav>
        <div className="flex items-center gap-1">
          <ThemeToggle />
          <Bell_ inbox={inbox} />
        </div>
      </header>

      <header className="flex h-14 shrink-0 items-center justify-between gap-2 border-b border-white/[0.06] bg-navy ps-4 pe-2 text-slate-100 md:hidden">
        <Link href="/dashboard" className="flex items-center gap-2.5 rounded-lg">
          <BrandMark size="sm" className="size-8 text-sm" />
          <span className="text-base font-extrabold">وی‌آی</span>
        </Link>
        <div className="flex items-center gap-0.5">
          <ThemeToggle onDark />
          <Bell_ inbox={inbox} onDark />
          <UserMenu variant="compact" />
          {showMenuButton && (
            <button
              type="button"
              onClick={onOpenMenu}
              aria-expanded={menuOpen}
              aria-label="منو"
              className="flex size-10 items-center justify-center rounded-xl text-slate-300 transition-colors hover:bg-white/10 hover:text-white"
            >
              <Menu className="size-5" />
            </button>
          )}
        </div>
      </header>
    </>
  );
}
