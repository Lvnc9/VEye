"use client";

import { Suspense, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { SetupBanner } from "@/components/SetupBanner";
import { ForcedPasswordScreen } from "@/components/account/ForcedPasswordScreen";
import { BottomNav } from "@/components/shell/BottomNav";
import { SidebarContent } from "@/components/shell/Sidebar";
import { TopBar } from "@/components/shell/TopBar";
import { Sheet } from "@/components/ui/Sheet";
import { ToastProvider } from "@/components/ui/Toast";
import { CurrentUserProvider, useCurrentUser } from "@/lib/current-user";
import { hidesBottomNav } from "@/lib/nav";
import { useInboxSummary } from "@/lib/use-inbox-summary";

/** While HR's password stands (Phase 20) the API answers nothing else, so neither does the app. */
function Shell({ children }: { children: React.ReactNode }) {
  const { user } = useCurrentUser();
  if (user?.must_change_password) return <ForcedPasswordScreen />;
  return (
    // useSearchParams (the bottom bar steps aside for an open conversation) needs a Suspense boundary.
    <Suspense>
      <AppShell>{children}</AppShell>
    </Suspense>
  );
}

/**
 * The signed-in frame (UI 2). From `md` up: the navy sidebar (collapsible to a rail) beside a column of
 * the frosted top bar and the page. Below `md`: the navy top bar, the page, and a bottom tab bar; the full
 * menu is a sheet from the start edge (the right, in RTL).
 *
 * A window-height shell in which only <main> scrolls: with `min-h-screen` the shell grew with its
 * content, so <main>'s overflow never engaged and a `sticky` bar inside it had nothing to stick to.
 * <main>'s padding stays as it was — the designer's full-bleed header offsets itself by it.
 */
function AppShell({ children }: { children: React.ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const inbox = useInboxSummary(); // one poll, shared by the sidebar, the top bar and the bottom bar
  const pathname = usePathname();
  const search = useSearchParams();
  const bottomNavHidden = hidesBottomNav(pathname, search);

  return (
    <div className="flex h-dvh overflow-hidden bg-canvas">
      <aside
        aria-label="منوی اصلی"
        className="hidden w-64 shrink-0 transition-[width] duration-300 ease-out-quint md:block md:rail:w-[4.75rem]"
      >
        <SidebarContent inbox={inbox} place="desktop" />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar inbox={inbox} onOpenMenu={() => setMenuOpen(true)} menuOpen={menuOpen} showMenuButton={bottomNavHidden} />
        <main className="relative min-w-0 flex-1 overflow-y-auto bg-canvas p-4 sm:p-6 md:p-8">
          {/* A soft wash of the brand colour at the top of every page; it scrolls away with the content. */}
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 top-0 -z-0 h-72 bg-[radial-gradient(60%_100%_at_70%_0%,color-mix(in_oklch,var(--primary)_7%,transparent),transparent)]"
          />
          <div className="relative">
            <SetupBanner />
            {children}
          </div>
        </main>
        {!bottomNavHidden && <BottomNav inbox={inbox} onOpenMenu={() => setMenuOpen(true)} menuOpen={menuOpen} />}
      </div>

      <Sheet open={menuOpen} onOpenChange={setMenuOpen} label="منوی اصلی" className="md:hidden">
        <SidebarContent inbox={inbox} place="sheet" onNavigate={() => setMenuOpen(false)} />
      </Sheet>
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
