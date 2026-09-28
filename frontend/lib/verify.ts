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

/** Per verdict: the seal's colours, the band across the top of the result card, and its text colour. */
export const VERIFY_STYLES: Record<VerifyState, { badge: string; band: string; text: string }> = {
  valid: {
    badge: "bg-emerald-500 text-white shadow-[0_8px_24px_-6px_rgb(16_185_129/0.6)] ring-8 ring-emerald-500/15",
    band: "from-emerald-500 to-teal-400",
    text: "text-emerald-700",
  },
  obsolete: {
    badge: "bg-rose-500 text-white shadow-[0_8px_24px_-6px_rgb(244_63_94/0.6)] ring-8 ring-rose-500/15",
    band: "from-rose-500 to-orange-400",
    text: "text-rose-700",
  },
  pending: {
    badge: "bg-amber-500 text-white shadow-[0_8px_24px_-6px_rgb(245_158_11/0.6)] ring-8 ring-amber-500/15",
    band: "from-amber-500 to-yellow-400",
    text: "text-amber-700",
  },
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
