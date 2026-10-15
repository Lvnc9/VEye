"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutGroup, m } from "motion/react";
import { PanelRightClose, PanelRightOpen, X } from "lucide-react";
import { unreadBadge, type InboxSummary } from "@/lib/chat";
import { useCurrentUser } from "@/lib/current-user";
import { activeHref } from "@/lib/nav";
import { BrandMark } from "@/components/ui/BrandMark";
import { CountBadge } from "@/components/ui/Badge";
import { Tooltip } from "@/components/ui/Tooltip";
import { cx } from "@/components/ui/cx";
import { navItemsFor } from "./nav";
import { UserMenu } from "./UserMenu";
import { useSidebarState } from "./useSidebarState";

const GLIDE = { type: "spring", stiffness: 380, damping: 34, mass: 0.8 } as const;

/**
 * What the navy sidebar holds: the brand, the grouped navigation and the signed-in person. Drawn twice by
 * the shell — as the desktop column (`place="desktop"`, collapsible to an icon rail) and inside the
 * phone's menu sheet (`place="sheet"`, with a close button; links close the sheet).
 *
 * The rail is CSS: `md:rail:*` classes apply while <html data-sidebar="collapsed">, and only from `md`
 * up, so the phone sheet always shows labels.
 */
export function SidebarContent({
  inbox,
  place,
  onNavigate,
}: {
  inbox: InboxSummary | null;
  place: "desktop" | "sheet";
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const { user, can } = useCurrentUser();
  const [rail, toggleRail] = useSidebarState();
  const collapsed = place === "desktop" && rail === "collapsed";

  const items = navItemsFor(user).filter((item) => !item.capability || can(item.capability));
  const current = activeHref(
    items.filter((item) => item.ready).map((item) => item.href),
    pathname,
  );
  const badge = unreadBadge(inbox?.total ?? 0);

  return (
    <div className="relative flex h-full flex-col overflow-hidden bg-sidebar text-sidebar-foreground">
      {/* A faint glow of the brand colour behind the logo, and a lit seam along the inner edge. */}
      <div aria-hidden className="pointer-events-none absolute -top-24 -right-20 size-72 rounded-full bg-glow/10 blur-3xl" />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-y-0 end-0 w-px bg-gradient-to-b from-transparent via-glow/20 to-transparent"
      />

      <div className="relative flex items-center justify-between gap-3 px-5 pt-5 pb-4 md:rail:justify-center md:rail:px-0">
        <Link href="/dashboard" onClick={onNavigate} className="flex min-w-0 items-center gap-3 rounded-xl">
          <BrandMark size="sm" />
          <span className="min-w-0 md:rail:hidden">
            <span className="block text-base font-extrabold leading-6 text-white">وی‌آی</span>
            <span className="block truncate text-xs text-slate-400">{user?.company?.name ?? "سامانه کنترل مستندات"}</span>
          </span>
        </Link>
        {place === "sheet" && (
          <button
            type="button"
            onClick={onNavigate}
            className="flex size-9 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-white/10 hover:text-white"
            aria-label="بستن منو"
          >
            <X className="size-5" />
          </button>
        )}
      </div>

      <LayoutGroup id={`sidebar-${place}`}>
        <nav
          aria-label="منوی اصلی"
          className="relative flex flex-1 flex-col overflow-y-auto overflow-x-hidden px-3 pb-4 [scrollbar-color:var(--color-navy-line)_transparent]"
        >
          {items.map((item, index) => {
            const Icon = item.icon;
            const startsGroup = index === 0 || items[index - 1].group !== item.group;
            const heading = startsGroup ? (
              <>
                <p className={cx("mb-1.5 px-3 text-[11px] font-bold text-slate-500 md:rail:hidden", index === 0 ? "mt-1" : "mt-5")}>
                  {item.group}
                </p>
                {index > 0 && <span aria-hidden className="mx-auto my-3 hidden h-px w-6 bg-white/10 md:rail:block" />}
              </>
            ) : null;

            if (!item.ready) {
              return (
                <div key={item.href}>
                  {heading}
                  <span
                    className="flex h-10 cursor-not-allowed items-center gap-3 rounded-lg px-3 text-sm text-slate-600"
                    title="در فاز بعدی افزوده می‌شود"
                  >
                    <Icon className="size-[18px]" />
                    <span className="flex-1 truncate">{item.label}</span>
                    <span className="text-[10px] text-slate-600">به‌زودی</span>
                  </span>
                </div>
              );
            }

            const active = item.href === current;
            const isInbox = item.href === "/inbox";
            return (
              <div key={item.href}>
                {heading}
                <Tooltip content={item.label} side="left" disabled={!collapsed}>
                  <Link
                    href={item.href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    aria-label={collapsed ? item.label : undefined}
                    className={cx(
                      "group relative flex h-10 items-center gap-3 rounded-lg px-3 text-sm transition-colors duration-150",
                      "md:rail:justify-center md:rail:px-0",
                      active ? "text-white" : "text-slate-400 hover:bg-white/[0.05] hover:text-slate-100",
                    )}
                  >
                    {active && (
                      <m.span
                        layoutId="nav-active"
                        transition={GLIDE}
                        aria-hidden
                        className="absolute inset-0 rounded-lg bg-gradient-to-l from-white/[0.1] to-white/[0.04] ring-1 ring-inset ring-white/[0.06]"
                      >
                        <span className="absolute inset-y-2 -start-3 w-1 rounded-e-full bg-glow shadow-[0_0_12px_rgb(56_189_248/0.7)] md:rail:-start-[0.85rem]" />
                      </m.span>
                    )}
                    <span className="relative">
                      <Icon
                        className={cx(
                          "size-[18px] transition-colors duration-150",
                          active ? "text-glow drop-shadow-[0_0_6px_rgb(56_189_248/0.5)]" : "text-slate-500 group-hover:text-slate-300",
                        )}
                      />
                      {isInbox && badge && (
                        <span aria-hidden className="absolute -top-1 -end-1 hidden size-2 rounded-full bg-rose-500 ring-2 ring-sidebar md:rail:block" />
                      )}
                    </span>
                    <span className="relative flex-1 truncate md:rail:sr-only">{item.label}</span>
                    {isInbox && badge && (
                      <CountBadge
                        label={`${inbox?.total} مورد در کارتابل`}
                        className="relative animate-pop shadow-[0_0_0_2px_var(--sidebar),0_2px_8px_-2px_rgb(225_29_72/0.6)] md:rail:hidden"
                      >
                        {badge}
                      </CountBadge>
                    )}
                  </Link>
                </Tooltip>
              </div>
            );
          })}
        </nav>
      </LayoutGroup>

      <div className="relative space-y-1 border-t border-sidebar-border p-3">
        <UserMenu variant="sidebar" onNavigate={onNavigate} />
        {place === "desktop" && (
          <Tooltip content="باز کردن منو" side="left" disabled={!collapsed}>
            <button
              type="button"
              onClick={toggleRail}
              aria-label={collapsed ? "باز کردن منو" : "جمع کردن منو"}
              className="flex h-9 w-full items-center gap-3 rounded-lg px-3 text-xs text-slate-500 transition-colors hover:bg-white/[0.05] hover:text-slate-200 md:rail:justify-center md:rail:px-0"
            >
              {collapsed ? <PanelRightOpen className="size-[18px]" /> : <PanelRightClose className="size-[18px]" />}
              <span className="md:rail:hidden">جمع کردن منو</span>
            </button>
          </Tooltip>
        )}
      </div>
    </div>
  );
}
