import type { ComponentType } from "react";
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
  Megaphone,
  PieChart,
  Settings,
  ShieldAlert,
  UserPlus,
} from "lucide-react";
import type { Capability, User } from "@/lib/types";

export interface NavItem {
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
export function navItemsFor(user: User | null): NavItem[] {
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

/** The phone's bottom tab bar: the four places people go most, then «منو» for the rest. */
export const PHONE_TABS: { href: string; label: string; icon: ComponentType<{ className?: string }> }[] = [
  { href: "/dashboard", label: "داشبورد", icon: LayoutDashboard },
  { href: "/inbox", label: "کارتابل", icon: Inbox },
  { href: "/documents", label: "مستندات", icon: FilePlus2 },
  { href: "/projects", label: "پروژه‌ها", icon: FolderKanban },
];
