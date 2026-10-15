import type { ReactNode } from "react";

import { buttonClass } from "@/components/ui/Button";
import { navyControlClass } from "@/components/ui/Field";

/** Shared look of the dark public pages (setup wizard) — the navy variants of the app's own parts. */
export const darkInput = `${navyControlClass} w-full py-2.5`;

export const primaryButton = buttonClass({ variant: "glow", size: "md", className: "rounded-xl px-5" });

export const ghostButton = buttonClass({ variant: "navy-ghost", size: "md", className: "rounded-xl" });

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
    <section className="veye-glass rounded-3xl p-6 sm:p-8">
      <h2 className="text-xl font-extrabold text-slate-50">{title}</h2>
      {intro && <p className="mt-2 text-sm leading-7 text-slate-400">{intro}</p>}
      <div className="mt-6 space-y-5">{children}</div>
    </section>
  );
}
