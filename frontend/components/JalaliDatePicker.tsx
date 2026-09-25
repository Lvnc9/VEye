"use client";

import { useEffect, useRef, useState } from "react";
import {
  JALALI_MONTHS,
  JALALI_WEEKDAYS_SHORT,
  addJalaliDays,
  addJalaliMonths,
  formatJalaliDMY,
  isoToJalali,
  jalaliMonthGrid,
  jalaliMonthLength,
  jalaliOf,
  jalaliToIso,
  toPersianDigits,
  type JalaliDate,
} from "@/lib/jalali";

interface Props {
  /** ISO "YYYY-MM-DD" (what the API takes); `""`/null = empty. */
  value: string | null | undefined;
  onChange: (iso: string | null) => void;
  /** Goes on the trigger button, so `<label htmlFor>` works. */
  id?: string;
  /** Inclusive ISO bounds; days outside are disabled. */
  min?: string;
  max?: string;
  disabled?: boolean;
  /** Hides «پاک کردن». */
  required?: boolean;
  placeholder?: string;
  /** Classes for the trigger; defaults to the app's input look. */
  className?: string;
  "aria-describedby"?: string;
}

const DEFAULT_TRIGGER = "w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm";

/**
 * A Jalali date picker (Phase 10; the owner asked for هجری شمسی instead of the browser's Gregorian
 * `<input type="date">`). Hand-rolled — the frontend takes no date dependency. The value stays ISO, so
 * nothing changes for the API; only what the user sees and clicks is Jalali, shown day-month-year.
 *
 * Keyboard: the trigger opens it; in the grid ←/→ move a day (RTL: ← is the next day), ↑/↓ a week,
 * Enter picks, Esc closes. On a phone the calendar is a fixed panel across the screen rather than a
 * dropdown, so it never runs off the edge of a 375px viewport.
 */
export function JalaliDatePicker({
  value,
  onChange,
  id,
  min,
  max,
  disabled,
  required,
  placeholder = "انتخاب تاریخ",
  className,
  "aria-describedby": describedBy,
}: Props) {
  const selected = isoToJalali(value || null);
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<{ jy: number; jm: number }>(() => {
    const start = selected ?? jalaliOf(new Date());
    return { jy: start.jy, jm: start.jm };
  });
  const [focus, setFocus] = useState<JalaliDate | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const gridRef = useRef<HTMLDivElement>(null);

  const today = jalaliOf(new Date());
  const inRange = (iso: string) => (!min || iso >= min) && (!max || iso <= max);

  function openPicker() {
    const start = selected ?? today;
    setView({ jy: start.jy, jm: start.jm });
    setFocus(start);
    setOpen(true);
  }

  function close(returnFocus = true) {
    setOpen(false);
    if (returnFocus) triggerRef.current?.focus();
  }

  function pick(day: JalaliDate) {
    const iso = jalaliToIso(day.jy, day.jm, day.jd);
    if (!inRange(iso)) return;
    onChange(iso);
    close();
  }

  function moveFocus(days: number) {
    const from = focus ?? selected ?? today;
    const next = addJalaliDays(from, days);
    setFocus(next);
    if (next.jy !== view.jy || next.jm !== view.jm) setView({ jy: next.jy, jm: next.jm });
  }

  function showMonth(months: number) {
    const next = addJalaliMonths(view.jy, view.jm, months);
    setView(next);
    // Keep the keyboard cursor inside the month on screen.
    if (focus) setFocus({ ...next, jd: Math.min(focus.jd, jalaliMonthLength(next.jy, next.jm)) });
  }

  // Close on a click outside (the listener only exists while open).
  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  // Move DOM focus to the keyboard cursor's day (no state is set here).
  useEffect(() => {
    if (!open || !focus) return;
    const cell = gridRef.current?.querySelector<HTMLButtonElement>(`[data-day="${focus.jy}-${focus.jm}-${focus.jd}"]`);
    cell?.focus();
  }, [open, focus]);

  function onGridKeyDown(event: React.KeyboardEvent) {
    const step: Record<string, number> = { ArrowLeft: 1, ArrowRight: -1, ArrowDown: 7, ArrowUp: -7 };
    if (event.key in step) {
      event.preventDefault();
      moveFocus(step[event.key]);
    }
  }

  const years = yearOptions(view.jy, min, max);
  const grid = jalaliMonthGrid(view.jy, view.jm);
  const todayIso = jalaliToIso(today.jy, today.jm, today.jd);

  return (
    <div ref={rootRef} className="relative" onKeyDown={(event) => event.key === "Escape" && open && close()}>
      <button
        ref={triggerRef}
        id={id}
        type="button"
        disabled={disabled}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-describedby={describedBy}
        onClick={() => (open ? close(false) : openPicker())}
        className={`${className ?? DEFAULT_TRIGGER} flex items-center justify-between gap-2 text-start disabled:opacity-50`}
      >
        <span className={selected ? "text-slate-900" : "text-slate-400"}>
          {selected ? formatJalaliDMY(selected.jy, selected.jm, selected.jd) : placeholder}
        </span>
        <CalendarIcon />
      </button>

      {open && (
        <>
          {/* Phone: dim the page behind the fixed panel; a tap on it closes. */}
          <div className="fixed inset-0 z-30 bg-slate-900/20 sm:hidden" onClick={() => close(false)} aria-hidden />
          <div
            role="dialog"
            aria-label="انتخاب تاریخ"
            className="fixed inset-x-4 top-24 z-40 rounded-lg border border-slate-200 bg-white p-3 shadow-lg sm:absolute sm:inset-x-auto sm:start-0 sm:top-full sm:mt-1 sm:w-72"
          >
            <div className="mb-2 flex items-center gap-1">
              <button
                type="button"
                onClick={() => showMonth(-1)}
                aria-label="ماه قبل"
                className="rounded px-2 py-1 text-slate-600 hover:bg-slate-100"
              >
                ›
              </button>
              <select
                aria-label="ماه"
                value={view.jm}
                onChange={(event) => setView({ jy: view.jy, jm: Number(event.target.value) })}
                className="min-w-0 flex-1 rounded border border-slate-200 bg-white px-1 py-1 text-sm"
              >
                {JALALI_MONTHS.map((name, index) => (
                  <option key={name} value={index + 1}>
                    {name}
                  </option>
                ))}
              </select>
              <select
                aria-label="سال"
                value={view.jy}
                onChange={(event) => setView({ jy: Number(event.target.value), jm: view.jm })}
                className="w-20 rounded border border-slate-200 bg-white px-1 py-1 text-sm"
              >
                {years.map((year) => (
                  <option key={year} value={year}>
                    {toPersianDigits(year)}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => showMonth(1)}
                aria-label="ماه بعد"
                className="rounded px-2 py-1 text-slate-600 hover:bg-slate-100"
              >
                ‹
              </button>
            </div>

            <div className="grid grid-cols-7 text-center text-xs text-slate-500" aria-hidden>
              {JALALI_WEEKDAYS_SHORT.map((name) => (
                <span key={name} className="py-1">
                  {name}
                </span>
              ))}
            </div>
            <div ref={gridRef} className="grid grid-cols-7 gap-0.5" onKeyDown={onGridKeyDown}>
              {grid.map((day, index) => {
                if (day === null) return <span key={`pad-${index}`} />;
                const date = { jy: view.jy, jm: view.jm, jd: day };
                const iso = jalaliToIso(view.jy, view.jm, day);
                const isSelected = !!selected && selected.jy === view.jy && selected.jm === view.jm && selected.jd === day;
                const isFocus = !!focus && focus.jy === view.jy && focus.jm === view.jm && focus.jd === day;
                const allowed = inRange(iso);
                return (
                  <button
                    key={iso}
                    type="button"
                    data-day={`${view.jy}-${view.jm}-${day}`}
                    tabIndex={isFocus ? 0 : -1}
                    disabled={!allowed}
                    aria-pressed={isSelected}
                    aria-label={formatJalaliDMY(view.jy, view.jm, day)}
                    onClick={() => pick(date)}
                    className={`rounded py-1.5 text-sm tabular-nums disabled:cursor-not-allowed disabled:text-slate-300 ${
                      isSelected
                        ? "bg-slate-900 font-semibold text-white"
                        : iso === todayIso
                          ? "font-semibold text-slate-900 ring-1 ring-slate-400 hover:bg-slate-100"
                          : "text-slate-700 hover:bg-slate-100"
                    }`}
                  >
                    {toPersianDigits(day)}
                  </button>
                );
              })}
            </div>

            <div className="mt-2 flex items-center justify-between border-t border-slate-100 pt-2 text-xs">
              <button
                type="button"
                onClick={() => pick(today)}
                disabled={!inRange(todayIso)}
                className="rounded px-2 py-1 text-slate-700 hover:bg-slate-100 disabled:opacity-40"
              >
                امروز
              </button>
              {!required && selected && (
                <button
                  type="button"
                  onClick={() => {
                    onChange(null);
                    close();
                  }}
                  className="rounded px-2 py-1 text-red-600 hover:bg-red-50"
                >
                  پاک کردن
                </button>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

/** Ten years either side of the month on screen, clipped to min/max. */
function yearOptions(current: number, min?: string, max?: string): number[] {
  const low = Math.max(current - 10, isoToJalali(min)?.jy ?? -Infinity);
  const high = Math.min(current + 10, isoToJalali(max)?.jy ?? Infinity);
  const years: number[] = [];
  for (let year = low; year <= high; year += 1) years.push(year);
  return years.includes(current) ? years : [current, ...years];
}

function CalendarIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 shrink-0 text-slate-400" aria-hidden>
      <rect x="3" y="4.5" width="14" height="12" rx="1.5" />
      <path d="M3 8.5h14M7 3v3M13 3v3" strokeLinecap="round" />
    </svg>
  );
}
