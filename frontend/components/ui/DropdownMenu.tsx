"use client";

import type { ComponentProps, ReactNode } from "react";
import { Check, ChevronLeft } from "lucide-react";
import { DropdownMenu as M } from "radix-ui";
import { cx } from "./cx";

/**
 * A menu of actions under a trigger (Radix): arrow keys, type-ahead, Escape, right-to-left sub-menus.
 * Compose it — `<DropdownMenu trigger={<button…/>}><MenuItem …/></DropdownMenu>`. An item that opens a
 * dialog should set state in `onSelect`; the menu closes first, then the dialog takes focus.
 */
export function DropdownMenu({
  trigger,
  children,
  align = "end",
  side = "bottom",
  className,
  modal = true,
}: {
  /** One element that can take a ref (a button). */
  trigger: ReactNode;
  children: ReactNode;
  align?: "start" | "center" | "end";
  side?: "top" | "bottom" | "left" | "right";
  className?: string;
  modal?: boolean;
}) {
  return (
    <M.Root modal={modal}>
      <M.Trigger asChild>{trigger}</M.Trigger>
      <M.Portal>
        <M.Content align={align} side={side} sideOffset={6} collisionPadding={8} className={cx(menuPanel, "min-w-48", className)}>
          {children}
        </M.Content>
      </M.Portal>
    </M.Root>
  );
}

const menuPanel =
  "z-[60] overflow-hidden rounded-xl border border-border bg-popover/95 p-1.5 text-popover-foreground shadow-overlay backdrop-blur-xl " +
  "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 " +
  "data-[side=bottom]:slide-in-from-top-1 data-[side=top]:slide-in-from-bottom-1 " +
  "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95";

const itemClass =
  "relative flex cursor-pointer select-none items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm outline-none transition-colors " +
  "data-[highlighted]:bg-accent data-[highlighted]:text-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50 " +
  "[&_svg]:size-4 [&_svg]:text-muted-foreground pointer-coarse:py-3";

export function MenuItem({
  icon,
  children,
  tone = "neutral",
  className,
  ...rest
}: ComponentProps<typeof M.Item> & { icon?: ReactNode; tone?: "neutral" | "danger" }) {
  return (
    <M.Item
      className={cx(
        itemClass,
        tone === "danger" && "text-rose-700 data-[highlighted]:bg-rose-50 data-[highlighted]:text-rose-700 dark:text-rose-400 dark:data-[highlighted]:bg-rose-500/10 [&_svg]:text-current",
        className,
      )}
      {...rest}
    >
      {icon}
      <span className="min-w-0 flex-1 truncate">{children}</span>
    </M.Item>
  );
}

/** A choice among a few (the theme): the picked one shows a check. */
export function MenuRadioGroup<T extends string>({
  value,
  onChange,
  items,
}: {
  value: T;
  onChange: (value: T) => void;
  items: { value: T; label: ReactNode; icon?: ReactNode }[];
}) {
  return (
    <M.RadioGroup value={value} onValueChange={(next) => onChange(next as T)}>
      {items.map((item) => (
        <M.RadioItem key={item.value} value={item.value} className={itemClass}>
          {item.icon}
          <span className="flex-1">{item.label}</span>
          <M.ItemIndicator>
            <Check className="!text-primary" />
          </M.ItemIndicator>
        </M.RadioItem>
      ))}
    </M.RadioGroup>
  );
}

export function MenuLabel({ children }: { children: ReactNode }) {
  return <M.Label className="px-2.5 pt-1.5 pb-1 text-xs text-muted-foreground">{children}</M.Label>;
}

export function MenuSeparator() {
  return <M.Separator className="-mx-1.5 my-1.5 h-px bg-border" />;
}

/** A nested menu; it opens toward the reading direction's end (the left, in RTL). */
export function MenuSub({ label, icon, children }: { label: ReactNode; icon?: ReactNode; children: ReactNode }) {
  return (
    <M.Sub>
      <M.SubTrigger className={cx(itemClass, "data-[state=open]:bg-accent")}>
        {icon}
        <span className="flex-1">{label}</span>
        <ChevronLeft className="size-4" />
      </M.SubTrigger>
      <M.Portal>
        <M.SubContent sideOffset={6} collisionPadding={8} className={cx(menuPanel, "min-w-40")}>
          {children}
        </M.SubContent>
      </M.Portal>
    </M.Sub>
  );
}
