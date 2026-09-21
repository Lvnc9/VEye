import type { ReactNode } from "react";

/** Shared look of the dark public pages (setup wizard). */
export const darkInput =
  "w-full rounded-lg border border-line bg-surface px-3.5 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 " +
  "focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30 disabled:opacity-50";

export const primaryButton =
  "rounded-lg bg-accent px-5 py-2.5 text-sm font-bold text-slate-950 transition-colors hover:bg-accent-strong disabled:opacity-50";

export const ghostButton =
  "rounded-lg border border-line px-4 py-2.5 text-sm text-slate-300 transition-colors hover:bg-white/5 disabled:opacity-50";

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
        <p role="alert" className="mt-1 text-xs text-red-300">
          {error}
        </p>
      )}
    </div>
  );
}

export function DarkError({ message }: { message: string }) {
  return (
    <div role="alert" className="rounded-lg border border-red-500/40 bg-red-500/10 px-3.5 py-2.5 text-sm text-red-200">
      {message}
    </div>
  );
}

export function StepCard({ title, intro, children }: { title: string; intro?: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-line bg-surface-raised p-6 sm:p-8">
      <h2 className="text-xl font-bold text-slate-50">{title}</h2>
      {intro && <p className="mt-2 text-sm leading-7 text-slate-400">{intro}</p>}
      <div className="mt-6 space-y-5">{children}</div>
    </section>
  );
}
