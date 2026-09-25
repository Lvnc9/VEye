import { describe, expect, it } from "vitest";
import {
  addJalaliDays,
  addJalaliMonths,
  formatJalali,
  formatJalaliDMY,
  formatJalaliDateTime,
  isJalaliLeapYear,
  isoToJalali,
  jalaliMonthGrid,
  jalaliMonthLength,
  jalaliToIso,
  jalaliWeekday,
  toGregorian,
  toJalali,
} from "./jalali";

// The platform's persian calendar with Latin digits, to compare numbers.
const INTL = new Intl.DateTimeFormat("en-US-u-ca-persian-nu-latn", { year: "numeric", month: "numeric", day: "numeric" });
function intlJalali(date: Date) {
  const parts = Object.fromEntries(INTL.formatToParts(date).map((p) => [p.type, p.value]));
  return { jy: Number.parseInt(parts.year, 10), jm: Number(parts.month), jd: Number(parts.day) };
}

describe("Jalali arithmetic agrees with Intl", () => {
  it("for every day from 1370 to 1430, both ways", () => {
    // 1 Farvardin 1370 = 21 March 1991; walk day by day to the end of 1430.
    const date = new Date(1991, 2, 21);
    let checked = 0;
    const mismatches: string[] = [];
    for (;;) {
      const expected = intlJalali(date);
      if (expected.jy > 1430) break;
      const gy = date.getFullYear();
      const gm = date.getMonth() + 1;
      const gd = date.getDate();
      const actual = toJalali(gy, gm, gd);
      if (actual.jy !== expected.jy || actual.jm !== expected.jm || actual.jd !== expected.jd) {
        mismatches.push(`${gy}-${gm}-${gd}: ${JSON.stringify(actual)} vs ${JSON.stringify(expected)}`);
      }
      const back = toGregorian(actual.jy, actual.jm, actual.jd);
      if (back.gy !== gy || back.gm !== gm || back.gd !== gd) mismatches.push(`round trip ${gy}-${gm}-${gd}`);
      checked += 1;
      date.setDate(date.getDate() + 1);
      if (mismatches.length > 5) break;
    }
    expect(mismatches).toEqual([]);
    expect(checked).toBeGreaterThan(22000);
  });

  it("knows month lengths and leap years", () => {
    expect(jalaliMonthLength(1405, 1)).toBe(31);
    expect(jalaliMonthLength(1405, 7)).toBe(30);
    expect(isJalaliLeapYear(1403)).toBe(true);
    expect(jalaliMonthLength(1403, 12)).toBe(30);
    expect(isJalaliLeapYear(1404)).toBe(false);
    expect(jalaliMonthLength(1404, 12)).toBe(29);
  });
});

describe("ISO conversion (what the API speaks)", () => {
  it("round-trips a calendar date", () => {
    expect(isoToJalali("2026-09-25")).toEqual({ jy: 1405, jm: 7, jd: 3 });
    expect(jalaliToIso(1405, 7, 3)).toBe("2026-09-25");
    expect(jalaliToIso(1405, 1, 1)).toBe("2026-03-21");
  });

  it("rejects anything that is not YYYY-MM-DD", () => {
    expect(isoToJalali("")).toBeNull();
    expect(isoToJalali(null)).toBeNull();
    expect(isoToJalali("2026-09-25T10:00:00Z")).toBeNull();
  });
});

describe("calendar helpers", () => {
  it("puts 1 Farvardin 1405 (a Saturday) in the first column", () => {
    expect(jalaliWeekday(1405, 1, 1)).toBe(0);
    expect(jalaliWeekday(1405, 1, 7)).toBe(6); // جمعه
  });

  it("lays a month out in whole شنبه-first weeks", () => {
    const grid = jalaliMonthGrid(1405, 7); // 1 Mehr 1405 = Wednesday 23 Sept 2026 → column 4
    expect(grid.slice(0, 5)).toEqual([null, null, null, null, 1]);
    expect(grid.filter((cell) => cell !== null)).toHaveLength(30);
    expect(grid.length % 7).toBe(0);
    expect(jalaliMonthGrid(1405, 1)[0]).toBe(1); // starts on شنبه: no padding
  });

  it("moves across month and year boundaries", () => {
    expect(addJalaliDays({ jy: 1404, jm: 12, jd: 29 }, 1)).toEqual({ jy: 1405, jm: 1, jd: 1 });
    expect(addJalaliDays({ jy: 1405, jm: 7, jd: 1 }, -1)).toEqual({ jy: 1405, jm: 6, jd: 31 });
    expect(addJalaliMonths(1405, 12, 1)).toEqual({ jy: 1406, jm: 1 });
    expect(addJalaliMonths(1405, 1, -1)).toEqual({ jy: 1404, jm: 12 });
  });
});

// U+2066 LEFT-TO-RIGHT ISOLATE … U+2069 POP DIRECTIONAL ISOLATE (see isolateLtr).
const LRI = "\u2066";
const PDI = "\u2069";

describe("display is day-month-year (owner, 2026-09-25)", () => {
  it("formats a calendar date day first, with Persian digits", () => {
    expect(formatJalali("2026-09-25")).toBe(`${LRI}۰۳-۰۷-۱۴۰۵${PDI}`);
    expect(formatJalaliDMY(1405, 7, 3)).toBe(`${LRI}۰۳-۰۷-۱۴۰۵${PDI}`);
  });

  it("is a left-to-right isolate of Persian digits and hyphens only", () => {
    // Without the isolate, a hyphenated date after Persian letters renders with its groups reversed.
    expect(formatJalali("2026-03-21")).toMatch(/^\u2066[۰-۹]{2}-[۰-۹]{2}-[۰-۹]{4}\u2069$/);
  });

  it("puts the time after the date for timestamps", () => {
    expect(formatJalaliDateTime(new Date(2026, 8, 25, 16, 30))).toBe(`${LRI}۰۳-۰۷-۱۴۰۵${PDI} ۱۶:۳۰`);
  });

  it("returns an empty string for nothing or garbage", () => {
    expect(formatJalali(null)).toBe("");
    expect(formatJalali("not a date")).toBe("");
  });
});
