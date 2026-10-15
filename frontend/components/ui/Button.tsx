import type { ComponentProps, ReactNode } from "react";
import { cva } from "class-variance-authority";
import { Slot } from "radix-ui";
import { Spinner } from "./Spinner";
import { cx } from "./cx";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "subtle" | "danger" | "danger-ghost" | "glow" | "navy-ghost";
export type ButtonSize = "xs" | "sm" | "md" | "lg";

/**
 * Every button's look (UI 2). `glow` and `navy-ghost` are for the navy surfaces (sign-in, setup); the rest
 * read the semantic tokens, so they follow the theme. The primary carries a soft top highlight and lifts a
 * glow of its own colour on hover.
 */
const buttonVariants = cva(
  "relative inline-flex select-none items-center justify-center gap-2 whitespace-nowrap rounded-lg font-medium " +
    "transition-[background-color,border-color,color,box-shadow,scale,opacity] duration-150 ease-out " +
    "active:scale-[0.97] disabled:pointer-events-none disabled:opacity-50 " +
    // A finger needs a 44px target; a mouse keeps the compact size.
    "pointer-coarse:min-h-11",
  {
    variants: {
      variant: {
        primary:
          "bg-primary font-bold text-primary-foreground shadow-[inset_0_1px_0_rgb(255_255_255/0.16),0_1px_2px_rgb(3_105_161/0.3)] " +
          "hover:bg-primary-hover hover:shadow-[inset_0_1px_0_rgb(255_255_255/0.16),0_8px_20px_-8px_var(--primary)]",
        secondary:
          "border border-input bg-card text-soft-foreground shadow-xs hover:border-slate-400 hover:bg-accent hover:text-foreground " +
          "dark:hover:border-white/25",
        ghost: "text-soft-foreground hover:bg-accent hover:text-foreground",
        subtle: "bg-primary/10 font-bold text-primary hover:bg-primary/15",
        danger:
          "bg-destructive font-bold text-destructive-foreground shadow-[inset_0_1px_0_rgb(255_255_255/0.14),0_1px_2px_rgb(225_29_72/0.3)] " +
          "hover:bg-rose-700 hover:shadow-[inset_0_1px_0_rgb(255_255_255/0.14),0_8px_20px_-8px_var(--color-rose-600)] dark:hover:bg-rose-400",
        "danger-ghost": "text-rose-700 hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-500/10",
        glow:
          "bg-glow font-bold text-navy shadow-[0_8px_24px_-8px_rgb(56_189_248/0.6)] hover:bg-glow-strong " +
          "hover:shadow-[0_10px_28px_-8px_rgb(56_189_248/0.75)]",
        "navy-ghost": "border border-navy-line text-slate-300 hover:bg-white/5 hover:text-white",
      },
      size: {
        xs: "h-7 rounded-md px-2.5 text-xs [&_svg]:size-3.5",
        sm: "h-8 px-3 text-sm [&_svg]:size-4",
        md: "h-10 px-4 text-sm [&_svg]:size-4",
        lg: "h-11 rounded-xl px-6 text-base [&_svg]:size-5",
      },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

/** The class list of a button — also for a `<Link>` that should look like one. */
export function buttonClass({
  variant = "secondary",
  size = "md",
  className,
}: { variant?: ButtonVariant; size?: ButtonSize; className?: string } = {}): string {
  return cx(buttonVariants({ variant, size }), className);
}

interface ButtonProps extends ComponentProps<"button"> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Shows a spinner in place of the icon and disables the button. */
  loading?: boolean;
  /** A leading lucide icon (it sits on the right, before the label, in RTL). */
  icon?: ReactNode;
  /** Render the one child (a `<Link>`, an `<a>`) with the button's look instead of a `<button>`. */
  asChild?: boolean;
}

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  icon,
  asChild = false,
  className,
  children,
  disabled,
  type = "button",
  ...rest
}: ButtonProps) {
  if (asChild) {
    return (
      <Slot.Root className={buttonClass({ variant, size, className })} {...rest}>
        {children}
      </Slot.Root>
    );
  }
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
