import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/**
 * tailwind-merge taught our own scales (app/globals.css), so `shadow-card` and `shadow-raised` are known
 * to conflict and the later one wins. A new custom shadow, easing or animation token must be added here
 * too — lib/utils.test.ts holds the list.
 */
const twMerge = extendTailwindMerge({
  extend: {
    theme: {
      shadow: ["xs", "card", "raised", "overlay"],
      ease: ["out-quint", "in-quart"],
      animate: ["fade-up", "fade-in", "scale-in", "pop"],
    },
  },
});

/**
 * Joins class names, dropping the falsy ones, and lets a later Tailwind class override an earlier one
 * of the same kind — `cn("h-10 px-4", small && "h-8")` gives `px-4 h-8`. The shadcn/21st.dev helper.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
