"use client";

import { useEffect, useState, type ComponentType } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Building2,
  CalendarDays,
  CircleUserRound,
  ClipboardCheck,
  FilePlus2,
  FolderKanban,
  Gauge,
  History,
  Inbox,
  LayoutDashboard,
  LogOut,
  Megaphone,
  Menu,
  PieChart,
  Settings,
  ShieldAlert,
  UserPlus,
  X,
} from "lucide-react";
import { apiPost } from "@/lib/api-client";
import { SetupBanner } from "@/components/SetupBanner";
import { Avatar } from "@/components/ui/Avatar";
import { CountBadge } from "@/components/ui/Badge";
import { BrandMark } from "@/components/ui/BrandMark";
import { cx } from "@/components/ui/cx";
import { ToastProvider } from "@/components/ui/Toast";
import { unreadBadge } from "@/lib/chat";
import { CurrentUserProvider, useCurrentUser } from "@/lib/current-user";
import { useInboxSummary } from "@/lib/use-inbox-summary";
import type { InboxSummary } from "@/lib/chat";
import type { Capability, User } from "@/lib/types";

interface NavItem {
  href: string;
  label: string;
  ready: boolean;
  capability?: Capability;
  icon: ComponentType<{ className?: string }>;
  /** The quiet heading the item sits under; items keep their order, a heading starts where it changes. */
  group: string;
}

/**
 * The sidebar. The company's entry is labelled with the company's own name, so this is a function of
 * the current user (whose `/auth/me/` carries the company) rather than a constant.
 * `ready: false` marks routes whose screens arrive in a later phase — they render as disabled rather
 * than as links that 404. `capability` hides an entry the current user could not use anyway.
 */
function navItemsFor(user: User | null): NavItem[] {
  return [
    { href: "/dashboard", label: "داشبورد", ready: true, icon: LayoutDashboard, group: "میز کار" },
    { href: "/inbox", label: "کارتابل", ready: true, icon: Inbox, group: "میز کار" },
    {
      href: "/organization",
      label: user?.company?.name ?? "ساختار سازمان",
      ready: true,
      icon: Building2,
      group: "سازمان و پروژه‌ها",
    },
    { href: "/projects", label: "پروژه‌ها", ready: true, icon: FolderKanban, group: "سازمان و پروژه‌ها" },
    { href: "/documents", label: "ساخت مستند", ready: true, icon: FilePlus2, group: "مستندات" },
    { href: "/documents/history", label: "سوابق مستندات", ready: true, icon: History, group: "مستندات" },
    {
      href: "/reports",
      label: "گزارش‌ها",
      ready: true,
      capability: "view_reports",
      icon: PieChart,
      group: "مستندات",
    },
    { href: "/quality", label: "عدم‌انطباق‌ها", ready: true, icon: ShieldAlert, group: "کیفیت" },
    { href: "/quality/audits", label: "ممیزی‌ها", ready: true, icon: ClipboardCheck, group: "کیفیت" },
    { href: "/quality/risks", label: "ریسک‌ها", ready: true, icon: Gauge, group: "کیفیت" },
    { href: "/announcements", label: "اطلاعیه‌ها", ready: true, icon: Megaphone, group: "کارکنان" },
    { href: "/leave", label: "مرخصی", ready: true, icon: CalendarDays, group: "کارکنان" },
    {
      href: "/personnel/register",
      label: "ثبت پرسنل",
      ready: true,
      capability: "manage_personnel",
      icon: UserPlus,
      group: "مدیریت",
    },
    { href: "/settings", label: "تنظیمات", ready: true, icon: Settings, group: "مدیریت" },
    { href: "/account", label: "اکانت", ready: true, icon: CircleUserRound, group: "مدیریت" },
  ];
}

/**
 * From `md` up the sidebar is the fixed column it always was. Below it (phones, narrow windows) it is
 * a drawer from the start side — the right, in RTL — opened from the top bar, so the page keeps the
 * whole width instead of a sliver next to a 15rem column. Closed, it is `invisible`, which also takes
 * its links out of the tab order; the visibility change waits for the slide to finish.
 */
function Sidebar({ inbox, open, onClose }: { inbox: InboxSummary | null; open: boolean; onClose: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, can } = useCurrentUser();

  // The most specific matching item is the active one, so /documents/history
  // doesn't also light up «ساخت مستند» (whose href is a prefix of it).
  const navItems = navItemsFor(user);
  const activeHref = navItems.filter(
    (item) =>
      item.ready &&
      (pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href + "/"))),
  ).sort((a, b) => b.href.length - a.href.length)[0]?.href;

  async function handleLogout() {
    onClose();
    try {
      await apiPost("/auth/logout/");
    } catch {
      // Ignore network/API errors — we still want to send the user to /login.
    } finally {
      router.push("/login");
    }
  }

  const visible = navItems.filter((item) => !item.capability || can(item.capability));
  const badge = unreadBadge(inbox?.total ?? 0);

  return (
    <aside
      id="app-sidebar"
      aria-label="منوی اصلی"
      className={cx(
        "fixed inset-y-0 right-0 z-40 flex w-72 max-w-[85vw] flex-col overflow-hidden bg-surface text-slate-100",
        "transition-[translate,visibility,box-shadow] md:static md:z-auto md:w-64 md:max-w-none md:flex-shrink-0",
        "md:visible md:translate-x-0 md:shadow-none md:transition-none",
        open
          ? "visible translate-x-0 shadow-overlay duration-300 ease-out-quint"
          : "invisible translate-x-full duration-200 ease-in-quart",
      )}
    >
      {/* A faint glow of the brand colour behind the logo, as on the sign-in page. */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-24 -right-20 size-72 rounded-full bg-accent/10 blur-3xl"
      />

      <div className="relative flex items-center justify-between gap-3 px-5 pt-5 pb-4">
        <Link href="/dashboard" onClick={onClose} className="flex min-w-0 items-center gap-3 rounded-xl">
          <BrandMark size="sm" />
          <span className="min-w-0">
            <span className="block text-base font-bold leading-6 text-white">وی‌آی</span>
            <span className="block truncate text-xs text-slate-400">{user?.company?.name ?? "سامانه کنترل مستندات"}</span>
          </span>
        </Link>
        <button
          type="button"
          onClick={onClose}
          className="flex size-9 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-white/10 hover:text-white md:hidden"
          aria-label="بستن منو"
        >
          <X className="size-5" />
        </button>
      </div>

      <nav className="relative flex flex-1 flex-col overflow-y-auto px-3 pb-4 [scrollbar-color:var(--color-line)_transparent]">
        {visible.map((item, index) => {
          const Icon = item.icon;
          const heading =
            index === 0 || visible[index - 1].group !== item.group ? (
              <p className={cx("mb-1.5 px-3 text-[11px] font-bold text-slate-500", index === 0 ? "mt-1" : "mt-5")}>
                {item.group}
              </p>
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
          const active = item.href === activeHref;
          return (
            <div key={item.href}>
              {heading}
              <Link
                href={item.href}
                onClick={onClose}
                aria-current={active ? "page" : undefined}
                className={cx(
                  "group relative flex h-10 items-center gap-3 rounded-lg px-3 text-sm transition-[background-color,color] duration-150",
                  active ? "bg-white/[0.08] text-white" : "text-slate-400 hover:bg-white/[0.05] hover:text-slate-100",
                )}
              >
                {active && (
                  <span
                    aria-hidden
                    className="absolute inset-y-2 -right-3 w-1 rounded-l-full bg-accent shadow-[0_0_12px_rgb(56_189_248/0.6)] animate-fade-in"
                  />
                )}
                <Icon
                  className={cx(
                    "size-[18px] transition-colors duration-150",
                    active ? "text-accent" : "text-slate-500 group-hover:text-slate-300",
                  )}
                />
                <span className="flex-1 truncate">{item.label}</span>
                {item.href === "/inbox" && badge && (
                  <CountBadge label={`${inbox?.total} مورد در کارتابل`} className="animate-pop">
                    {badge}
                  </CountBadge>
                )}
              </Link>
            </div>
          );
        })}
      </nav>

      <div className="relative border-t border-white/[0.06] p-3">
        <div className="flex items-center gap-3 rounded-xl px-2 py-2">
          {user ? <Avatar name={user.full_name} size="md" className="ring-2 ring-white/10" /> : <span className="size-9" />}
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm leading-6 text-slate-100">{user?.full_name ?? "\u00a0"}</p>
            <p className="truncate text-xs text-slate-500">{user?.title ?? "\u00a0"}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={handleLogout}
          className="mt-1 flex h-10 w-full items-center gap-3 rounded-lg px-3 text-sm text-slate-400 transition-colors duration-150 hover:bg-rose-500/10 hover:text-rose-300"
        >
          <LogOut className="rtl-flip size-[18px]" />
          خروج
        </button>
      </div>
    </aside>
  );
}

/** Only below `md`: the brand and the button that opens the sidebar drawer (with the کارتابل count,
 *  since the drawer that carries it is hidden). */
function TopBar({ inbox, open, onOpen }: { inbox: InboxSummary | null; open: boolean; onOpen: () => void }) {
  const badge = unreadBadge(inbox?.total ?? 0);
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-white/[0.06] bg-surface px-4 text-slate-100 md:hidden">
      <Link href="/dashboard" className="flex items-center gap-2.5 rounded-lg">
        <BrandMark size="sm" className="size-8 text-sm" />
        <span className="text-base font-bold">وی‌آی</span>
      </Link>
      <button
        type="button"
        onClick={onOpen}
        aria-controls="app-sidebar"
        aria-expanded={open}
        className="flex h-10 items-center gap-2 rounded-lg bg-white/[0.06] px-3 text-sm transition-colors hover:bg-white/10 active:scale-[0.97]"
      >
        <Menu className="size-5" />
        منو
        {badge && <CountBadge label={`${inbox?.total} مورد در کارتابل`}>{badge}</CountBadge>}
      </button>
    </header>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const inbox = useInboxSummary(); // one poll, shared by the sidebar and the top bar

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    // A window-height shell in which only <main> scrolls. With `min-h-screen`
    // the shell grew with its content, so <main>'s overflow never engaged: long
    // pages scrolled the whole window (dragging the sidebar's log-out button to
    // the bottom of the page) and a `sticky` bar inside <main> had nothing to
    // stick to.
    <div className="flex h-dvh flex-col overflow-hidden bg-canvas md:flex-row">
      <TopBar inbox={inbox} open={open} onOpen={() => setOpen(true)} />
      <Sidebar inbox={inbox} open={open} onClose={() => setOpen(false)} />
      {/* The backdrop stays mounted so it can fade out as well as in. */}
      <div
        aria-hidden="true"
        onClick={() => setOpen(false)}
        className={cx(
          "fixed inset-0 z-30 bg-slate-950/50 backdrop-blur-[2px] transition-opacity md:hidden",
          open ? "opacity-100 duration-300" : "pointer-events-none opacity-0 duration-200",
        )}
      />
      <main className="min-w-0 flex-1 overflow-y-auto bg-canvas p-4 sm:p-6 md:p-8">
        <SetupBanner />
        {children}
      </main>
    </div>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <CurrentUserProvider>
      <ToastProvider>
        <Shell>{children}</Shell>
      </ToastProvider>
    </CurrentUserProvider>
  );
}
