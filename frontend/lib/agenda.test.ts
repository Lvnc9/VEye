import { describe, expect, it } from "vitest";
import { itemsByDay, monthCells, monthWindow, type AgendaItem } from "./agenda";

const item = (over: Partial<AgendaItem>): AgendaItem => ({
  key: "k",
  kind: "objective",
  kind_label: "",
  date: "2026-10-14",
  end_date: null,
  title: "t",
  subtitle: "",
  url: "",
  overdue: false,
  ...over,
});

describe("monthWindow", () => {
  it("spans a Jalali month in Gregorian dates", () => {
    expect(monthWindow(1405, 7)).toEqual({ from: "2026-09-23", to: "2026-10-22" }); // مهر ۱۴۰۵, 30 days
    expect(monthWindow(1405, 12)).toEqual({ from: "2027-02-20", to: "2027-03-20" }); // اسفند, 29 days
  });
});

describe("monthCells", () => {
  it("pads to whole weeks and puts an ISO date on every real day", () => {
    const cells = monthCells(1405, 7);
    expect(cells.length % 7).toBe(0);
    const real = cells.filter((c) => c.day !== null);
    expect(real).toHaveLength(30);
    expect(real[0].iso).toBe("2026-09-23");
    expect(real[29].iso).toBe("2026-10-22");
    expect(cells.filter((c) => c.day === null).every((c) => c.iso === null)).toBe(true);
  });
});

describe("itemsByDay", () => {
  it("puts a one-day item on its day", () => {
    const byDay = itemsByDay([item({ date: "2026-10-14" })], "2026-10-01", "2026-10-31");
    expect(Object.keys(byDay)).toEqual(["2026-10-14"]);
  });

  it("repeats a span on every day it covers", () => {
    const byDay = itemsByDay([item({ kind: "leave", date: "2026-10-14", end_date: "2026-10-16" })], "2026-10-01", "2026-10-31");
    expect(Object.keys(byDay)).toEqual(["2026-10-14", "2026-10-15", "2026-10-16"]);
  });

  it("clips a span to the window on both sides", () => {
    const byDay = itemsByDay([item({ date: "2026-09-29", end_date: "2026-10-03" })], "2026-10-01", "2026-10-02");
    expect(Object.keys(byDay)).toEqual(["2026-10-01", "2026-10-02"]);
  });

  it("ignores items wholly outside the window and keeps order within a day", () => {
    const a = item({ key: "a", date: "2026-10-05" });
    const b = item({ key: "b", date: "2026-10-05" });
    const out = item({ key: "c", date: "2026-11-05" });
    const byDay = itemsByDay([a, b, out], "2026-10-01", "2026-10-31");
    expect(byDay["2026-10-05"].map((i) => i.key)).toEqual(["a", "b"]);
    expect(Object.keys(byDay)).toEqual(["2026-10-05"]);
  });
});
