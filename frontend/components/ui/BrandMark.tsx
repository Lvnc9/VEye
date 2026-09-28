import { cx } from "./cx";

/** The «وی» tile — VEye's mark on the navy surfaces (sidebar, login, setup). */
export function BrandMark({ size = "md", className }: { size?: "sm" | "md" | "lg"; className?: string }) {
  const box = { sm: "size-9 rounded-lg text-base", md: "size-10 rounded-xl text-lg", lg: "size-11 rounded-xl text-xl" }[size];
  return (
    <span
      aria-hidden
      className={cx(
        "flex shrink-0 items-center justify-center border border-line bg-gradient-to-b from-surface-raised to-surface font-bold text-accent",
        "shadow-[inset_0_1px_0_rgb(255_255_255/0.06),0_0_0_1px_rgb(56_189_248/0.06),0_8px_24px_-8px_rgb(56_189_248/0.35)]",
        box,
        className,
      )}
    >
      وی
    </span>
  );
}
