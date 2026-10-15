"use client";

import { useMemo, type ReactNode } from "react";
import { CircleAlert, CircleCheck } from "lucide-react";
import { Toaster, toast as sonner } from "sonner";

type ToastTone = "success" | "danger";
interface ToastMessage {
  tone: ToastTone;
  title: string;
  detail?: string;
}

const DURATION_MS = 3200;

function show({ tone, title, detail }: ToastMessage) {
  const options = { description: detail, duration: DURATION_MS };
  if (tone === "danger") sonner.error(title, options);
  else sonner.success(title, options);
}

/** Shows a short notice at the bottom of the screen: `const toast = useToast(); toast({ title: "…" })`. */
export function useToast() {
  return useMemo(() => show, []);
}

/**
 * Mounted once around the app: draws the notices (sonner). Up to three stack, newest in front, each going
 * away by itself; hovering keeps them. Above the phone's bottom bar.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  return (
    <>
      {children}
      <Toaster
        dir="rtl"
        position="bottom-center"
        visibleToasts={3}
        offset={24}
        mobileOffset={{ bottom: "calc(5rem + env(safe-area-inset-bottom))" }}
        icons={{
          success: <CircleCheck className="size-4 text-emerald-600 dark:text-emerald-400" />,
          error: <CircleAlert className="size-4 text-rose-600 dark:text-rose-400" />,
        }}
        toastOptions={{
          unstyled: true,
          classNames: {
            toast:
              "flex w-full items-start gap-3 rounded-2xl border border-border bg-popover/95 px-4 py-3 text-sm text-popover-foreground " +
              "shadow-overlay backdrop-blur-xl font-sans sm:w-[22rem]",
            icon: "mt-1 shrink-0",
            content: "min-w-0 space-y-0.5",
            title: "font-bold text-foreground",
            description: "leading-6 text-soft-foreground",
            success: "border-emerald-200 dark:border-emerald-400/25",
            error: "border-rose-200 dark:border-rose-400/25",
          },
        }}
      />
    </>
  );
}
