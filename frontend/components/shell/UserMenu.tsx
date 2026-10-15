"use client";

import { useRouter } from "next/navigation";
import { ChevronsUpDown, CircleUserRound, LogOut } from "lucide-react";
import { apiPost } from "@/lib/api-client";
import { useCurrentUser } from "@/lib/current-user";
import { Avatar } from "@/components/ui/Avatar";
import { DropdownMenu, MenuItem, MenuLabel, MenuSeparator } from "@/components/ui/DropdownMenu";
import { cx } from "@/components/ui/cx";

/**
 * The signed-in person, as a menu: their account and signing out. `variant="sidebar"` is the row at the
 * foot of the navy sidebar (just the avatar when the rail is collapsed); `variant="compact"` is the
 * avatar alone, for the phone's top bar.
 */
export function UserMenu({ variant, onNavigate }: { variant: "sidebar" | "compact"; onNavigate?: () => void }) {
  const router = useRouter();
  const { user } = useCurrentUser();

  async function logout() {
    onNavigate?.();
    try {
      await apiPost("/auth/logout/");
    } catch {
      // Ignore network/API errors — we still want to send the user to /login.
    } finally {
      router.push("/login");
    }
  }

  const trigger =
    variant === "sidebar" ? (
      <button
        type="button"
        aria-label="منوی کاربر"
        className={cx(
          "group flex w-full items-center gap-3 rounded-xl px-2 py-2 text-start transition-colors hover:bg-sidebar-accent",
          "data-[state=open]:bg-sidebar-accent md:rail:justify-center md:rail:px-0",
        )}
      >
        {user ? (
          <Avatar name={user.full_name} size="md" className="ring-2 ring-white/10" title="" />
        ) : (
          <span className="size-9 rounded-full bg-white/5" />
        )}
        <span className="min-w-0 flex-1 md:rail:hidden">
          <span className="block truncate text-sm leading-6 text-slate-100">{user?.full_name ?? " "}</span>
          <span className="block truncate text-xs text-slate-400">{user?.title ?? " "}</span>
        </span>
        <ChevronsUpDown className="size-4 text-slate-500 transition-colors group-hover:text-slate-300 md:rail:hidden" />
      </button>
    ) : (
      <button
        type="button"
        aria-label="منوی کاربر"
        className="flex size-10 items-center justify-center rounded-full transition-[scale] active:scale-95"
      >
        {user ? <Avatar name={user.full_name} size="md" className="ring-2 ring-white/15" title="" /> : <span className="size-9" />}
      </button>
    );

  return (
    <DropdownMenu trigger={trigger} side={variant === "sidebar" ? "top" : "bottom"} align={variant === "sidebar" ? "start" : "end"} className="w-60">
      {user && (
        <MenuLabel>
          <span className="block truncate text-sm font-bold text-foreground">{user.full_name}</span>
          {user.title && <span className="block truncate">{user.title}</span>}
        </MenuLabel>
      )}
      <MenuSeparator />
      <MenuItem
        icon={<CircleUserRound />}
        onSelect={() => {
          onNavigate?.();
          router.push("/account");
        }}
      >
        اکانت
      </MenuItem>
      <MenuSeparator />
      <MenuItem icon={<LogOut className="rtl-flip" />} tone="danger" onSelect={logout}>
        خروج
      </MenuItem>
    </DropdownMenu>
  );
}
