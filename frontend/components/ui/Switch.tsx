import type { ComponentProps } from "react";
import { cx } from "./cx";

/**
 * An on/off switch that is a real checkbox underneath (so it works in a form, with a <label>, and for
 * screen readers as "switch"). Pass `checked` + `onChange` like any checkbox.
 */
export function Switch({ className, ...rest }: Omit<ComponentProps<"input">, "type">) {
  return (
    <span className={cx("relative inline-flex h-6 w-11 shrink-0 items-center", className)}>
      <input type="checkbox" role="switch" className="peer absolute inset-0 z-10 cursor-pointer opacity-0 disabled:cursor-not-allowed" {...rest} />
      <span
        aria-hidden
        className={cx(
          "pointer-events-none absolute inset-0 rounded-full bg-input transition-colors duration-200",
          "peer-checked:bg-primary peer-focus-visible:ring-4 peer-focus-visible:ring-ring/25 peer-disabled:opacity-50",
        )}
      />
      <span
        aria-hidden
        className={cx(
          "pointer-events-none absolute start-0.5 size-5 rounded-full bg-white shadow-sm transition-[translate] duration-200 ease-out-quint",
          "peer-checked:-translate-x-5",
        )}
      />
    </span>
  );
}
