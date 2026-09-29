"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { CircleAlert, CircleCheck } from "lucide-react";
import { cx } from "./cx";

type ToastTone = "success" | "danger";
interface ToastMessage {
  id: number;
  tone: ToastTone;
  title: string;
  detail?: string;
}

const DURATION_MS = 3200;

const ToastContext = createContext<((toast: Omit<ToastMessage, "id">) => void) | null>(null);

/** Shows a short notice at the bottom of the screen: `const toast = useToast(); toast({ title: "…" })`. */
export function useToast() {
  const show = useContext(ToastContext);
  // Outside a provider (a unit test, an isolated component) a notice is simply not shown.
  return useMemo(() => show ?? (() => {}), [show]);
}

/** Mounted once around the app. A new notice replaces the one on screen and goes away by itself. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<ToastMessage | null>(null);
  const counter = useRef(0);

  const show = useCallback((toast: Omit<ToastMessage, "id">) => {
    counter.current += 1;
    setMessage({ ...toast, id: counter.current });
  }, []);

  useEffect(() => {
    if (!message) return;
    const timer = setTimeout(() => setMessage(null), DURATION_MS);
    return () => clearTimeout(timer);
  }, [message]);

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div
        role="status"
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-24 z-[60] flex justify-center px-4"
      >
        {message && (
          <div
            key={message.id}
            className={cx(
              "pointer-events-auto flex max-w-md items-start gap-3 rounded-2xl border bg-white px-4 py-3 text-sm shadow-overlay animate-fade-up",
              message.tone === "success" ? "border-emerald-200" : "border-rose-200",
            )}
          >
            {message.tone === "success" ? (
              <CircleCheck className="mt-1 size-4 shrink-0 text-emerald-600" />
            ) : (
              <CircleAlert className="mt-1 size-4 shrink-0 text-rose-600" />
            )}
            <div className="min-w-0 space-y-0.5">
              <p className="font-bold text-slate-900">{message.title}</p>
              {message.detail && <p className="leading-6 text-slate-600">{message.detail}</p>}
            </div>
          </div>
        )}
      </div>
    </ToastContext.Provider>
  );
}
