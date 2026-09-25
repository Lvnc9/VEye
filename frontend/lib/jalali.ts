/**
 * Jalali (Persian) date helpers.
 *
 * The API speaks ISO-8601 (`"2026-09-25"` for a calendar date, a UTC timestamp otherwise); Jalali is
 * presentation only and happens here. Two halves:
 *
 * - **Display** goes through the platform `Intl` implementation with the persian calendar, so there is
 *   no dependency to keep in sync. Since Phase 10 (decided with the owner, 2026-09-25) every date on
 *   screen reads **day-month-year**: `۲۵-۰۶-۱۴۰۵`. PDFs are formatted by the backend and do not change.
 * - **Arithmetic** (the date picker needs to go both ways and to know month lengths) uses the
 *   Borkowski/jalCal algorithm — the one jalaali-js (MIT) implements. `jalali.test.ts` checks it against
 *   `Intl` for every day from 1370 to 1430, so the picker and the display can never disagree.
 *
 * Relative imports only: vitest has no `@/` alias.
 */

const JALALI_PARTS = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

const JALALI_LONG = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  year: "numeric",
  month: "long",
  day: "numeric",
});

const TIME_ONLY = new Intl.DateTimeFormat("fa-IR", { hour: "2-digit", minute: "2-digit", hour12: false });

const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/;

function toDate(value: string | Date | null | undefined): Date | null {
  if (!value) return null;
  if (typeof value === "string") {
    // A bare "2026-09-19" is a calendar date (the server's DateFields). `new Date()` would read it as
    // UTC midnight, which is the *previous* day for anyone west of UTC — so build it as a local date.
    const match = DATE_ONLY.exec(value);
    if (match) return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  }
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

// ---------------------------------------------------------------------------------------------
// Display
// ---------------------------------------------------------------------------------------------

/** Renders Latin digits as Persian, for values that arrive pre-formatted. */
export function toPersianDigits(value: string | number): string {
  return String(value).replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[Number(d)]);
}

function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

/**
 * Wraps a date in a left-to-right isolate (U+2066 … U+2069) so it reads the same everywhere.
 *
 * Why: after Arabic-script letters («مهلت: ۰۳-۰۷-۱۴۰۵») the bidi algorithm turns Persian digits into
 * "Arabic numbers", and a hyphen between Arabic numbers does not join them — so each group is laid out
 * right-to-left and the year jumps to the left. On its own (a button, a table cell) the same string
 * reads day-first. The isolate makes the date one left-to-right unit in every context: day on the
 * left, as Iranian D-M-Y dates are printed. (The old "۱۴۰۵/۰۶/۲۵" never had this problem because "/"
 * *does* join Arabic numbers.) The marks are invisible and ignored by screen readers.
 */
export function isolateLtr(text: string): string {
  return `\u2066${text}\u2069`;
}

/** "۲۵-۰۶-۱۴۰۵" from Jalali parts — the one place the display order lives. */
export function formatJalaliDMY(jy: number, jm: number, jd: number): string {
  return isolateLtr(toPersianDigits(`${pad2(jd)}-${pad2(jm)}-${jy}`));
}

/** "۲۵-۰۶-۱۴۰۵" — a calendar date or the date part of a timestamp, day first. */
export function formatJalali(value: string | Date | null | undefined): string {
  const date = toDate(value);
  if (!date) return "";
  // formatToParts keeps only the numbers (no locale-inserted marks); Intl gives Persian digits already.
  const parts = Object.fromEntries(JALALI_PARTS.formatToParts(date).map((p) => [p.type, p.value]));
  return isolateLtr(`${parts.day}-${parts.month}-${parts.year}`);
}

/** "۲۵-۰۶-۱۴۰۵ ۱۶:۳۰" — a timestamp (feeds, messages). */
export function formatJalaliDateTime(value: string | Date | null | undefined): string {
  const date = toDate(value);
  if (!date) return "";
  return `${formatJalali(date)} ${TIME_ONLY.format(date)}`;
}

/** "۲۵ شهریور ۱۴۰۵" — for prose contexts. */
export function formatJalaliLong(value: string | Date | null | undefined): string {
  const date = toDate(value);
  if (!date) return "";
  return JALALI_LONG.format(date);
}

/** Today, for display ("۲۵-۰۶-۱۴۰۵"). */
export function todayJalali(): string {
  return formatJalali(new Date());
}

// ---------------------------------------------------------------------------------------------
// Arithmetic (for the date picker)
// ---------------------------------------------------------------------------------------------

export interface JalaliDate {
  jy: number;
  jm: number; // 1..12
  jd: number; // 1..31
}

export const JALALI_MONTHS = [
  "فروردین",
  "اردیبهشت",
  "خرداد",
  "تیر",
  "مرداد",
  "شهریور",
  "مهر",
  "آبان",
  "آذر",
  "دی",
  "بهمن",
  "اسفند",
] as const;

/** Saturday-first, the Iranian week. Index 0 = شنبه. */
export const JALALI_WEEKDAYS_SHORT = ["ش", "ی", "د", "س", "چ", "پ", "ج"] as const;

// Years where the 33-year leap pattern restarts (Borkowski).
const BREAKS = [-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210, 1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178];

const div = (a: number, b: number) => Math.trunc(a / b);
const mod = (a: number, b: number) => a - Math.trunc(a / b) * b;

/** Leap offset (0 = leap year), the Gregorian year it starts in, and the March day of 1 Farvardin. */
function jalCal(jy: number): { leap: number; gy: number; march: number } {
  const gy = jy + 621;
  if (jy < BREAKS[0] || jy >= BREAKS[BREAKS.length - 1]) throw new RangeError(`Jalali year out of range: ${jy}`);
  let leapJ = -14;
  let jp = BREAKS[0];
  let jump = 0;
  for (let i = 1; i < BREAKS.length; i += 1) {
    const jm = BREAKS[i];
    jump = jm - jp;
    if (jy < jm) break;
    leapJ += div(jump, 33) * 8 + div(mod(jump, 33), 4);
    jp = jm;
  }
  let n = jy - jp;
  leapJ += div(n, 33) * 8 + div(mod(n, 33) + 3, 4);
  if (mod(jump, 33) === 4 && jump - n === 4) leapJ += 1;
  const leapG = div(gy, 4) - div((div(gy, 100) + 1) * 3, 4) - 150;
  const march = 20 + leapJ - leapG;
  if (jump - n < 6) n = n - jump + div(jump + 4, 33) * 33;
  let leap = mod(mod(n + 1, 33) - 1, 4);
  if (leap === -1) leap = 4;
  return { leap, gy, march };
}

/** Gregorian date → Julian day number. */
function g2d(gy: number, gm: number, gd: number): number {
  const d = div((gy + div(gm - 8, 6) + 100100) * 1461, 4) + div(153 * mod(gm + 9, 12) + 2, 5) + gd - 34840408;
  return d - div(div(gy + 100100 + div(gm - 8, 6), 100) * 3, 4) + 752;
}

/** Julian day number → Gregorian date. */
function d2g(jdn: number): { gy: number; gm: number; gd: number } {
  let j = 4 * jdn + 139361631;
  j += div(div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908;
  const i = div(mod(j, 1461), 4) * 5 + 308;
  const gd = div(mod(i, 153), 5) + 1;
  const gm = mod(div(i, 153), 12) + 1;
  const gy = div(j, 1461) - 100100 + div(8 - gm, 6);
  return { gy, gm, gd };
}

function j2d(jy: number, jm: number, jd: number): number {
  const { gy, march } = jalCal(jy);
  return g2d(gy, 3, march) + (jm - 1) * 31 - div(jm, 7) * (jm - 7) + jd - 1;
}

function d2j(jdn: number): JalaliDate {
  const { gy } = d2g(jdn);
  let jy = gy - 621;
  const cal = jalCal(jy);
  let k = jdn - g2d(gy, 3, cal.march);
  if (k >= 0) {
    if (k <= 185) return { jy, jm: 1 + div(k, 31), jd: mod(k, 31) + 1 };
    k -= 186;
  } else {
    jy -= 1;
    k += 179;
    if (cal.leap === 1) k += 1;
  }
  return { jy, jm: 7 + div(k, 30), jd: mod(k, 30) + 1 };
}

export function isJalaliLeapYear(jy: number): boolean {
  return jalCal(jy).leap === 0;
}

export function jalaliMonthLength(jy: number, jm: number): number {
  if (jm <= 6) return 31;
  if (jm <= 11) return 30;
  return isJalaliLeapYear(jy) ? 30 : 29;
}

export function toJalali(gy: number, gm: number, gd: number): JalaliDate {
  return d2j(g2d(gy, gm, gd));
}

export function toGregorian(jy: number, jm: number, jd: number): { gy: number; gm: number; gd: number } {
  return d2g(j2d(jy, jm, jd));
}

/** A local Date's Jalali parts (the date the user sees on their own clock). */
export function jalaliOf(date: Date): JalaliDate {
  return toJalali(date.getFullYear(), date.getMonth() + 1, date.getDate());
}

/** "YYYY-MM-DD" (what the API takes) → Jalali parts; null for anything else. */
export function isoToJalali(iso: string | null | undefined): JalaliDate | null {
  const match = iso ? DATE_ONLY.exec(iso) : null;
  if (!match) return null;
  return toJalali(Number(match[1]), Number(match[2]), Number(match[3]));
}

/** Jalali parts → "YYYY-MM-DD" (what the API takes). */
export function jalaliToIso(jy: number, jm: number, jd: number): string {
  const { gy, gm, gd } = toGregorian(jy, jm, jd);
  return `${gy}-${pad2(gm)}-${pad2(gd)}`;
}

/** Column of a Jalali date in a Saturday-first week (0 = شنبه … 6 = جمعه). */
export function jalaliWeekday(jy: number, jm: number, jd: number): number {
  const { gy, gm, gd } = toGregorian(jy, jm, jd);
  return (new Date(gy, gm - 1, gd).getDay() + 1) % 7;
}

/** Move by whole days, across month and year boundaries. */
export function addJalaliDays(date: JalaliDate, days: number): JalaliDate {
  return d2j(j2d(date.jy, date.jm, date.jd) + days);
}

/** Month arithmetic for the picker's ‹ › buttons. */
export function addJalaliMonths(jy: number, jm: number, months: number): { jy: number; jm: number } {
  const index = jy * 12 + (jm - 1) + months;
  return { jy: Math.floor(index / 12), jm: (index % 12 + 12) % 12 + 1 };
}

/**
 * The picker's month as whole weeks: `null` pads the first week up to the 1st's weekday (شنبه-first)
 * and the last week up to جمعه, so the grid is always a multiple of 7 cells.
 */
export function jalaliMonthGrid(jy: number, jm: number): (number | null)[] {
  const cells: (number | null)[] = Array(jalaliWeekday(jy, jm, 1)).fill(null);
  for (let day = 1; day <= jalaliMonthLength(jy, jm); day += 1) cells.push(day);
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}
