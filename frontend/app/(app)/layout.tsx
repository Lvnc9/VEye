"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { apiPost } from "@/lib/api-client";
import { CurrentUserProvider, useCurrentUser } from "@/lib/current-user";
import type { Capability } from "@/lib/types";

/**
 * Sidebar mirrors the desktop app's nav (V_1.0 main.py:894-954).
 * `ready: false` marks routes whose screens arrive in a later phase — they
 * render as disabled rather than as links that 404.
 * `capability` hides an entry the current user could not use anyway.
 */
const NAV_ITEMS: {
  href: string;
  label: string;
  ready: boolean;
  capability?: Capability;
}[] = [
  { href: "/dashboard", label: "داشبورد", ready: true },
  { href: "/documents", label: "ساخت مستند", ready: true },
  { href: "/documents/history", label: "سوابق مستندات", ready: false },
  {
    href: "/personnel/register",
    label: "ثبت پرسنل",
    ready: true,
    capability: "manage_personnel",
  },
  { href: "/settings", label: "تنظیمات", ready: true },
  { href: "/account", label: "اکانت", ready: true },
];

function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, can } = useCurrentUser();

  async function handleLogout() {
    try {
      await apiPost("/auth/logout/");
    } catch {
      // Ignore network/API errors — we still want to send the user to /login.
    } finally {
      router.push("/login");
    }
  }

  return (
    <aside className="flex w-60 flex-shrink-0 flex-col bg-slate-900 text-slate-100">
      <div className="px-6 py-6">
        <div className="text-xl font-bold">وی‌آی</div>
        {user && (
          <div className="mt-2 text-xs text-slate-400">
            <div>{user.full_name}</div>
            <div>{user.title}</div>
          </div>
        )}
      </div>

      <nav className="flex flex-1 flex-col gap-1 px-3">
        {NAV_ITEMS.filter((item) => !item.capability || can(item.capability)).map((item) => {
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
          const active =
            pathname === item.href ||
            (item.href !== "/dashboard" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`rounded px-3 py-2 text-sm transition-colors ${
                active
                  ? "bg-slate-700 font-medium text-white"
                  : "text-slate-300 hover:bg-slate-800"
              }`}
            >
              {item.label}
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

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <CurrentUserProvider>
      {/* A window-height shell in which only <main> scrolls. With `min-h-screen`
          the shell grew with its content, so <main>'s overflow never engaged: long
          pages scrolled the whole window (dragging the sidebar's log-out button to
          the bottom of the page) and a `sticky` bar inside <main> had nothing to
          stick to. */}
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto bg-slate-50 p-8">{children}</main>
      </div>
    </CurrentUserProvider>
  );
}
