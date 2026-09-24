"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { apiPost } from "@/lib/api-client";
import { SetupBanner } from "@/components/SetupBanner";
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
}

/**
 * The sidebar. The company's entry is labelled with the company's own name, so this is a function of
 * the current user (whose `/auth/me/` carries the company) rather than a constant.
 * `ready: false` marks routes whose screens arrive in a later phase — they render as disabled rather
 * than as links that 404. `capability` hides an entry the current user could not use anyway.
 */
function navItemsFor(user: User | null): NavItem[] {
  return [
    { href: "/dashboard", label: "داشبورد", ready: true },
    { href: "/inbox", label: "کارتابل", ready: true },
    { href: "/organization", label: user?.company?.name ?? "ساختار سازمان", ready: true },
    { href: "/projects", label: "پروژه‌ها", ready: true },
    { href: "/documents", label: "ساخت مستند", ready: true },
    { href: "/documents/history", label: "سوابق مستندات", ready: true },
    { href: "/personnel/register", label: "ثبت پرسنل", ready: true, capability: "manage_personnel" },
    { href: "/settings", label: "تنظیمات", ready: true },
    { href: "/account", label: "اکانت", ready: true },
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

  return (
    <aside
      id="app-sidebar"
      aria-label="منوی اصلی"
      className={`fixed inset-y-0 right-0 z-40 flex w-64 max-w-[85vw] flex-col overflow-y-auto bg-slate-900 text-slate-100 shadow-xl transition-[translate,visibility] duration-200 md:static md:z-auto md:w-60 md:max-w-none md:flex-shrink-0 md:translate-x-0 md:shadow-none md:visible ${
        open ? "visible translate-x-0" : "invisible translate-x-full"
      }`}
    >
      <div className="px-6 py-6">
        <div className="flex items-center justify-between">
          <div className="text-xl font-bold">وی‌آی</div>
          <button
            type="button"
            onClick={onClose}
            className="rounded px-2 py-1 text-sm text-slate-300 hover:bg-slate-800 md:hidden"
            aria-label="بستن منو"
          >
            ✕
          </button>
        </div>
        {user && (
          <div className="mt-2 text-xs text-slate-400">
            <div>{user.full_name}</div>
            <div>{user.title}</div>
          </div>
        )}
      </div>

      <nav className="flex flex-1 flex-col gap-1 px-3">
        {navItems.filter((item) => !item.capability || can(item.capability)).map((item) => {
          if (!item.ready) {
            return (
              <span
                key={item.href}
                className="flex cursor-not-allowed items-center justify-between rounded px-3 py-2 text-sm text-slate-500"
                title="در فاز بعدی افزوده می‌شود"
              >
                {item.label}
                <span className="text-[10px] text-slate-600">به‌زودی</span>
              </span>
            );
          }
          const active = item.href === activeHref;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onClose}
              className={`rounded px-3 py-2 text-sm transition-colors ${
                active
                  ? "bg-slate-700 font-medium text-white"
                  : "text-slate-300 hover:bg-slate-800"
              }`}
            >
              <span className="flex items-center justify-between">
                {item.label}
                {item.href === "/inbox" && unreadBadge(inbox?.total ?? 0) && (
                  <span
                    className="rounded-full bg-red-600 px-1.5 py-0.5 text-[10px] font-bold text-white"
                    aria-label={`${inbox?.total} مورد در کارتابل`}
                  >
                    {unreadBadge(inbox?.total ?? 0)}
                  </span>
                )}
              </span>
            </Link>
          );
        })}
      </nav>

      <button
        onClick={handleLogout}
        className="mx-3 mb-6 rounded bg-slate-700 px-3 py-2 text-sm font-medium hover:bg-slate-600"
      >
        خروج
      </button>
    </aside>
  );
}

/** Only below `md`: the brand and the button that opens the sidebar drawer (with the کارتابل count,
 *  since the drawer that carries it is hidden). */
function TopBar({ inbox, open, onOpen }: { inbox: InboxSummary | null; open: boolean; onOpen: () => void }) {
  const badge = unreadBadge(inbox?.total ?? 0);
  return (
    <header className="flex items-center justify-between bg-slate-900 px-4 py-3 text-slate-100 md:hidden">
      <div className="text-lg font-bold">وی‌آی</div>
      <button
        type="button"
        onClick={onOpen}
        aria-controls="app-sidebar"
        aria-expanded={open}
        className="flex items-center gap-2 rounded bg-slate-800 px-3 py-1.5 text-sm hover:bg-slate-700"
      >
        منو
        {badge && (
          <span
            className="rounded-full bg-red-600 px-1.5 py-0.5 text-[10px] font-bold text-white"
            aria-label={`${inbox?.total} مورد در کارتابل`}
          >
            {badge}
          </span>
        )}
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
    <div className="flex h-screen flex-col overflow-hidden md:flex-row">
      <TopBar inbox={inbox} open={open} onOpen={() => setOpen(true)} />
      <Sidebar inbox={inbox} open={open} onClose={() => setOpen(false)} />
      {open && (
        <div aria-hidden="true" onClick={() => setOpen(false)} className="fixed inset-0 z-30 bg-slate-950/50 md:hidden" />
      )}
      <main className="min-w-0 flex-1 overflow-y-auto bg-slate-50 p-4 sm:p-6 md:p-8">
        <SetupBanner />
        {children}
      </main>
    </div>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <CurrentUserProvider>
      <Shell>{children}</Shell>
    </CurrentUserProvider>
  );
}
