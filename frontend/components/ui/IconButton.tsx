"use client";

import type { ComponentProps, ReactNode } from "react";
import { Tooltip } from "./Tooltip";
import { cx } from "./cx";

type Tone = "neutral" | "danger" | "brand" | "onDark";

const TONES: Record<Tone, string> = {
  neutral: "text-muted-foreground hover:bg-accent hover:text-foreground",
  danger: "text-muted-foreground hover:bg-rose-50 hover:text-rose-700 dark:hover:bg-rose-500/10 dark:hover:text-rose-400",
  brand: "text-primary hover:bg-primary/10",
  onDark: "text-slate-300 hover:bg-white/10 hover:text-white",
};

const SIZES = {
  sm: "size-8 [&_svg]:size-4",
  md: "size-9 [&_svg]:size-[18px]",
} as const;

interface Props extends Omit<ComponentProps<"button">, "aria-label"> {
  /** Read by screen readers and shown as the tooltip — an icon alone says nothing to them. */
  label: string;
  tone?: Tone;
  size?: keyof typeof SIZES;
  /** Where the tooltip appears (physical side). */
  tooltipSide?: "top" | "bottom" | "left" | "right";
  children: ReactNode;
}

/** A square, icon-only button with its label as a tooltip. On touch screens it grows to a 44px target. */
export function IconButton({
  label,
  tone = "neutral",
  size = "md",
  tooltipSide = "top",
  className,
  children,
  type = "button",
  disabled,
  ...rest
}: Props) {
  return (
    <Tooltip content={label} side={tooltipSide} disabled={disabled}>
      <button
        type={type}
        aria-label={label}
        disabled={disabled}
        className={cx(
          "inline-flex shrink-0 items-center justify-center rounded-lg transition-[background-color,color,scale] duration-150",
          "active:scale-90 disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-transparent disabled:active:scale-100",
          "pointer-coarse:size-11",
          SIZES[size],
          TONES[tone],
          className,
        )}
        {...rest}
      >
        {children}
      </button>
    </Tooltip>
  );
}
