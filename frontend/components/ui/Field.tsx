import type { ReactNode } from "react";
import { CircleAlert } from "lucide-react";
import { cx } from "./cx";

/** The shared look of every text box, select and text area: a hairline border that darkens on hover and
 *  a soft brand halo on focus. */
export const controlClass =
  "rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-900 shadow-xs " +
  "transition-[border-color,box-shadow,background-color] duration-150 placeholder:text-slate-400 " +
  "hover:border-slate-400 focus:border-brand-500 focus:outline-none focus:ring-4 focus:ring-brand-500/15 " +
  "focus-visible:outline-none disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500 " +
  "disabled:hover:border-slate-300 aria-[invalid=true]:border-rose-400 aria-[invalid=true]:focus:ring-rose-500/15";

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
      <label htmlFor={htmlFor} className="mb-1.5 block text-sm text-slate-700">
        {label}
        {required && (
          <span aria-hidden className="ms-0.5 text-rose-600">
            *
          </span>
        )}
      </label>
      {children}
      {hint && !error && <p className="mt-1.5 text-xs text-slate-500">{hint}</p>}
      {error && (
        <p role="alert" className={cx("mt-1.5 flex items-start gap-1 text-xs text-rose-700")}>
          <CircleAlert className="mt-0.5 size-3.5" />
          {error}
        </p>
      )}
    </div>
  );
}
