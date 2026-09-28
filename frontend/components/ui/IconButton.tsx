import type { ComponentProps, ReactNode } from "react";
import { cx } from "./cx";

type Tone = "neutral" | "danger" | "brand" | "onDark";

const TONES: Record<Tone, string> = {
  neutral: "text-slate-500 hover:bg-slate-100 hover:text-slate-900",
  danger: "text-slate-500 hover:bg-rose-50 hover:text-rose-700",
  brand: "text-brand-700 hover:bg-brand-50 hover:text-brand-800",
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
  children: ReactNode;
}

/** A square, icon-only button. On touch screens it grows to a 44px target. */
export function IconButton({ label, tone = "neutral", size = "md", className, children, type = "button", ...rest }: Props) {
  return (
    <button
      type={type}
      aria-label={label}
      title={label}
      className={cx(
        "inline-flex shrink-0 items-center justify-center rounded-lg transition-[background-color,color,transform] duration-150",
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
  );
}
