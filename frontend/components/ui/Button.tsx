import type { ComponentProps, ReactNode } from "react";
import { Spinner } from "./Spinner";
import { cx } from "./cx";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "subtle" | "danger" | "danger-ghost";
export type ButtonSize = "xs" | "sm" | "md" | "lg";

const BASE =
  "inline-flex select-none items-center justify-center gap-2 whitespace-nowrap rounded-lg " +
  "transition-[background-color,border-color,color,box-shadow,transform,opacity] duration-150 ease-out " +
  "active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100";

const VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "bg-brand-700 font-bold text-white shadow-[0_1px_2px_rgb(3_105_161/0.3),inset_0_1px_0_rgb(255_255_255/0.12)] " +
    "hover:bg-brand-800 disabled:hover:bg-brand-700",
  secondary:
    "border border-slate-300 bg-white text-slate-700 shadow-xs hover:border-slate-400 hover:bg-slate-50 hover:text-slate-900 " +
    "disabled:hover:border-slate-300 disabled:hover:bg-white",
  ghost: "text-slate-600 hover:bg-slate-100 hover:text-slate-900 disabled:hover:bg-transparent",
  subtle: "bg-brand-50 text-brand-800 hover:bg-brand-100 disabled:hover:bg-brand-50",
  danger:
    "bg-rose-600 font-bold text-white shadow-[0_1px_2px_rgb(225_29_72/0.3),inset_0_1px_0_rgb(255_255_255/0.12)] " +
    "hover:bg-rose-700 disabled:hover:bg-rose-600",
  "danger-ghost": "text-rose-700 hover:bg-rose-50 disabled:hover:bg-transparent",
};

const SIZES: Record<ButtonSize, string> = {
  xs: "h-7 rounded-md px-2.5 text-xs [&_svg]:size-3.5",
  sm: "h-8 px-3 text-sm [&_svg]:size-4",
  md: "h-10 px-4 text-sm [&_svg]:size-4",
  lg: "h-11 px-6 text-base [&_svg]:size-5",
};

/** The class list of a button — also for a `<Link>` that should look like one. */
export function buttonClass({
  variant = "secondary",
  size = "md",
  className,
}: { variant?: ButtonVariant; size?: ButtonSize; className?: string } = {}): string {
  return cx(BASE, VARIANTS[variant], SIZES[size], className);
}

interface ButtonProps extends ComponentProps<"button"> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Shows a spinner in place of the icon and disables the button. */
  loading?: boolean;
  /** A leading lucide icon (it sits on the right, before the label, in RTL). */
  icon?: ReactNode;
}

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  icon,
  className,
  children,
  disabled,
  type = "button",
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={buttonClass({ variant, size, className })}
      {...rest}
    >
      {loading ? <Spinner /> : icon}
      {children}
    </button>
  );
}
