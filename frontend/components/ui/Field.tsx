import type { ReactNode } from "react";
import { CircleAlert } from "lucide-react";

/** The shared look of every text box, select and text area: a hairline border that darkens on hover and
 *  a soft halo of the brand colour on focus. */
export const controlClass =
  "rounded-lg border border-input bg-card px-3 text-sm text-foreground shadow-xs " +
  "transition-[border-color,box-shadow,background-color] duration-150 placeholder:text-subtle-foreground " +
  "hover:border-slate-400 dark:hover:border-white/25 focus:border-ring focus:outline-none focus:ring-4 focus:ring-ring/20 " +
  "focus-visible:outline-none disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground " +
  "disabled:hover:border-input aria-[invalid=true]:border-rose-400 aria-[invalid=true]:focus:ring-rose-500/15";

/** The same control on the navy pages (sign-in, setup): a dark well with a glowing focus ring. */
export const navyControlClass =
  "rounded-xl border border-navy-line bg-navy/70 px-3.5 text-sm text-slate-100 placeholder:text-slate-500 " +
  "shadow-[inset_0_1px_2px_rgb(0_0_0/0.35)] transition-[border-color,box-shadow,background-color] duration-150 " +
  "hover:border-slate-600 focus:border-glow focus:bg-navy focus:outline-none focus:ring-4 focus:ring-glow/20 " +
  "focus-visible:outline-none disabled:opacity-50";

export const inputClass = `${controlClass} h-10 w-full`;
export const selectClass = `${controlClass} h-10`;
export const textareaClass = `${controlClass} w-full py-2 leading-7`;

/** A label over its control, with a hint under it — or the error, which replaces the hint. */
export function Field({
  label,
  htmlFor,
  hint,
  error,
  required,
  className,
  children,
}: {
  label: ReactNode;
  htmlFor?: string;
  hint?: ReactNode;
  error?: string | null;
  required?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={className}>
      <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium text-soft-foreground">
        {label}
        {required && (
          <span aria-hidden className="ms-0.5 text-destructive">
            *
          </span>
        )}
      </label>
      {children}
      {hint && !error && <p className="mt-1.5 text-xs text-muted-foreground">{hint}</p>}
      {error && (
        <p role="alert" className="mt-1.5 flex items-start gap-1 text-xs text-rose-700 animate-fade-in dark:text-rose-400">
          <CircleAlert className="mt-0.5 size-3.5" />
          {error}
        </p>
      )}
    </div>
  );
}
