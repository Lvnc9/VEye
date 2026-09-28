import type { ReactNode } from "react";

/** Shared look of the dark public pages (setup wizard). */
export const darkInput =
  "w-full rounded-xl border border-line bg-surface px-3.5 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 " +
  "transition-[border-color,box-shadow] duration-150 hover:border-slate-500/60 " +
  "focus:border-accent focus:outline-none focus:ring-4 focus:ring-accent/20 disabled:opacity-50";

export const primaryButton =
  "inline-flex items-center justify-center gap-2 rounded-xl bg-accent px-5 py-2.5 text-sm font-bold text-slate-950 " +
  "shadow-[0_8px_24px_-8px_rgb(56_189_248/0.6)] transition-[background-color,transform] duration-150 hover:bg-accent-strong " +
  "active:scale-[0.98] disabled:opacity-50 disabled:active:scale-100";

export const ghostButton =
  "inline-flex items-center justify-center gap-2 rounded-xl border border-line px-4 py-2.5 text-sm text-slate-300 " +
  "transition-[background-color,transform] duration-150 hover:bg-white/5 active:scale-[0.98] disabled:opacity-50";

export function Field({
  id,
  label,
  error,
  hint,
  children,
}: {
  id: string;
  label: string;
  error?: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-slate-300">
        {label}
      </label>
      {children}
      {hint && !error && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
      {error && (
        <p role="alert" className="mt-1 text-xs text-rose-300">
          {error}
        </p>
      )}
    </div>
  );
}

export function DarkError({ message }: { message: string }) {
  return (
    <div role="alert" className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-3.5 py-2.5 text-sm text-rose-200 animate-fade-in">
      {message}
    </div>
  );
}

export function StepCard({ title, intro, children }: { title: string; intro?: string; children: ReactNode }) {
  return (
    <section className="rounded-3xl border border-line bg-surface-raised p-6 shadow-[0_24px_64px_-24px_rgb(0_0_0/0.6)] sm:p-8">
      <h2 className="text-xl font-bold text-slate-50">{title}</h2>
      {intro && <p className="mt-2 text-sm leading-7 text-slate-400">{intro}</p>}
      <div className="mt-6 space-y-5">{children}</div>
    </section>
  );
}
