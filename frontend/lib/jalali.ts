/**
 * Jalali (Persian) date helpers.
 *
 * The domain is Jalali end to end: V_1.0 stamps documents with
 * jdatetime-formatted "%Y/%m/%d" strings like "1404/01/19", and the PDFs print
 * the same. Timestamps travel over the API as ISO-8601 UTC; conversion to
 * Jalali is presentation-only and happens here.
 *
 * Uses the platform Intl implementation with the islamic-solar ("persian")
 * calendar, so there is no extra dependency to keep in sync.
 */

const JALALI_NUMERIC = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

const JALALI_LONG = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  year: "numeric",
  month: "long",
  day: "numeric",
});

const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/;

function toDate(value: string | Date | null | undefined): Date | null {
  if (!value) return null;
  if (typeof value === "string") {
    // A bare "2026-09-19" is a calendar date (the server's change-log dates).
    // `new Date()` would read it as UTC midnight, which is the *previous* day
    // for anyone west of UTC — so build it as a local date instead.
    const match = DATE_ONLY.exec(value);
    if (match) return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  }
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** "۱۴۰۴/۰۱/۱۹" — the canonical document-date format. */
export function formatJalali(value: string | Date | null | undefined): string {
  const date = toDate(value);
  if (!date) return "";
  // Intl yields "۱۴۰۴/۰۱/۱۹" with Persian digits already.
  return JALALI_NUMERIC.format(date);
}

const TIME_ONLY = new Intl.DateTimeFormat("fa-IR", { hour: "2-digit", minute: "2-digit", hour12: false });

/** "۱۴۰۵/۰۶/۲۹ ۱۶:۳۰" — a timestamp (the audit feed). */
export function formatJalaliDateTime(value: string | Date | null | undefined): string {
  const date = toDate(value);
  if (!date) return "";
  return `${JALALI_NUMERIC.format(date)} ${TIME_ONLY.format(date)}`;
}

/** "۱۹ فروردین ۱۴۰۴" — for prose contexts. */
export function formatJalaliLong(value: string | Date | null | undefined): string {
  const date = toDate(value);
  if (!date) return "";
  return JALALI_LONG.format(date);
}

/** Today, in the storage format the backend and PDFs expect. */
export function todayJalali(): string {
  return formatJalali(new Date());
}

/** Renders Latin digits as Persian, for values that arrive pre-formatted. */
export function toPersianDigits(value: string | number): string {
  return String(value).replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[Number(d)]);
}
