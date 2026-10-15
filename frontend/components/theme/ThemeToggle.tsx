"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { THEME_LABELS, type ThemeChoice } from "@/lib/theme";
import { DropdownMenu, MenuLabel, MenuRadioGroup, MenuSeparator } from "@/components/ui/DropdownMenu";
import { Segmented } from "@/components/ui/Segmented";
import { cx } from "@/components/ui/cx";
import { useTheme } from "./ThemeProvider";

const CHOICES: { value: ThemeChoice; icon: React.ReactNode }[] = [
  { value: "light", icon: <Sun /> },
  { value: "dark", icon: <Moon /> },
  { value: "system", icon: <Monitor /> },
];

/**
 * The theme switch (UI 2): a button that shows a sun in light and a moon in dark — chosen by CSS (`dark:`),
 * so the server's light render never mismatches — and opens روشن / تیره / مطابق سیستم.
 */
export function ThemeToggle({ onDark = false }: { onDark?: boolean }) {
  const { choice, setChoice } = useTheme();
  return (
    <DropdownMenu
      align="end"
      className="w-48"
      trigger={
        <button
          type="button"
          aria-label="ظاهر: روشن، تیره یا مطابق سیستم"
          className={cx(
            "relative flex size-10 items-center justify-center rounded-xl transition-colors",
            onDark ? "text-slate-300 hover:bg-white/10 hover:text-white" : "text-muted-foreground hover:bg-accent hover:text-foreground",
          )}
        >
          <Sun className="size-[18px] transition-[rotate,scale] duration-300 dark:scale-0 dark:-rotate-90" />
          <Moon className="absolute size-[18px] scale-0 rotate-90 transition-[rotate,scale] duration-300 dark:scale-100 dark:rotate-0" />
        </button>
      }
    >
      <MenuLabel>ظاهر</MenuLabel>
      <MenuSeparator />
      <MenuRadioGroup
        value={choice}
        onChange={setChoice}
        items={CHOICES.map(({ value, icon }) => ({ value, icon, label: THEME_LABELS[value] }))}
      />
    </DropdownMenu>
  );
}

/** The same choice as a segmented control, for the account page. */
export function ThemeSegmented() {
  const { choice, setChoice } = useTheme();
  return (
    <Segmented<ThemeChoice>
      label="ظاهر"
      value={choice}
      onChange={setChoice}
      items={CHOICES.map(({ value, icon }) => [
        value,
        <span key={value} className="flex items-center justify-center gap-1.5 [&_svg]:size-4">
          {icon}
          {THEME_LABELS[value]}
        </span>,
      ] as const)}
    />
  );
}

