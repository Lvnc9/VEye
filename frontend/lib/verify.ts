/**
 * The public verify lookup (Phase 5): what a printed QR code opens.
 *
 * Deliberately not `apiGet`: the person scanning is not signed in, so there are
 * no cookies to send, no session to refresh, and a 401 must never bounce them
 * to the login page. Relative imports only (vitest has no `@/` alias).
 */
import type { VerifyResult, VerifyState } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export type VerifyOutcome =
  | { kind: "ok"; data: VerifyResult }
  | { kind: "not_found"; message: string }
  | { kind: "error"; message: string };

export const VERIFY_STYLES: Record<VerifyState, { badge: string; panel: string; icon: string }> = {
  valid: { badge: "bg-green-600 text-white", panel: "border-green-200 bg-green-50", icon: "✓" },
  obsolete: { badge: "bg-red-600 text-white", panel: "border-red-200 bg-red-50", icon: "✕" },
  pending: { badge: "bg-amber-500 text-white", panel: "border-amber-200 bg-amber-50", icon: "…" },
};

export async function fetchVerification(code: string): Promise<VerifyOutcome> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/verify/${encodeURIComponent(code)}/`, {
      cache: "no-store", // a verdict must never come from a cache
      credentials: "omit",
    });
  } catch {
    return { kind: "error", message: "ارتباط با سرور برقرار نشد. اتصال اینترنت را بررسی کنید." };
  }

  if (response.status === 404) {
    let message = "مستندی با این کد یافت نشد. کد را بررسی کنید.";
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      /* keep the default */
    }
    return { kind: "not_found", message };
  }
  if (response.status === 403 || response.status === 429) {
    return { kind: "error", message: "تعداد درخواست‌ها زیاد است. چند لحظه بعد دوباره تلاش کنید." };
  }
  if (!response.ok) {
    return { kind: "error", message: "بررسی مستند ممکن نشد. کمی بعد دوباره تلاش کنید." };
  }
  try {
    return { kind: "ok", data: (await response.json()) as VerifyResult };
  } catch {
    return { kind: "error", message: "پاسخ نامعتبر از سرور دریافت شد." };
  }
}
