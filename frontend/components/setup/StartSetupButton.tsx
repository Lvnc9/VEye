"use client";

import { useState } from "react";
import { ApiError, apiPost } from "@/lib/api-client";

/**
 * «شروع راه‌اندازی» for a signed-in مدیر عامل: one press creates the company (named «شرکت من» until
 * the wizard's first step renames it) with them at its root — no setup token, decided with the owner
 * 2026-09-23. The token form (AccountStep) stays for a fresh install, where nobody can sign in yet.
 */
export function StartSetupButton({
  onStarted,
  className,
  errorClassName,
}: {
  onStarted: () => void;
  className: string;
  errorClassName: string;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function start() {
    setBusy(true);
    setError(null);
    try {
      await apiPost("/setup/start/", {});
      onStarted();
    } catch (err) {
      // Someone else started it a moment ago: the wizard is where either of them wants to be.
      if (err instanceof ApiError && (err.data as { code?: string } | undefined)?.code === "already_bootstrapped") {
        onStarted();
        return;
      }
      setError(err instanceof ApiError ? err.message : "شروع راه‌اندازی ممکن نشد. اتصال را بررسی و دوباره تلاش کنید.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button type="button" onClick={start} disabled={busy} className={className}>
        {busy ? "در حال شروع..." : "شروع راه‌اندازی"}
      </button>
      {error && (
        <p role="alert" className={errorClassName}>
          {error}
        </p>
      )}
    </>
  );
}
