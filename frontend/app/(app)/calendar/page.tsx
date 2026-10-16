"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { CalendarRange, ChevronLeft, ChevronRight } from "lucide-react";
import {
  AGENDA_TONE,
  CHIPS_PER_DAY,
  itemsByDay,
  monthCells,
  monthWindow,
  type AgendaItem,
  type AgendaResponse,
} from "@/lib/agenda";
import {
  JALALI_MONTHS,
  JALALI_WEEKDAYS_SHORT,
  addJalaliMonths,
  formatJalali,
  jalaliOf,
  jalaliToIso,
  todayIso,
  toPersianDigits,
} from "@/lib/jalali";
import { useApiQuery } from "@/lib/use-api-query";
import { ErrorBanner } from "@/components/StatusBanner";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { Switch } from "@/components/ui/Switch";
import { cx } from "@/components/ui/cx";

/**
 * «تقویم» (Phase 22): a Jalali month of my dated work — objectives, corrective actions, meetings, audits,
 * risk and document reviews, my leave and cover, the official holidays — from `GET /agenda/`. A مسئول may add
 * «مرخصی تیم». Wide screens draw chips in each day; a phone draws dots. Either way, a day opens its list below.
 */
export default function CalendarPage() {
  const today = useMemo(() => jalaliOf(new Date()), []);
  const [view, setView] = useState({ jy: today.jy, jm: today.jm });
  const [team, setTeam] = useState(false);
  const [selected, setSelected] = useState<string>(todayIso());
  const window_ = monthWindow(view.jy, view.jm);
  const agenda = useApiQuery<AgendaResponse>(
    `/agenda/?from=${window_.from}&to=${window_.to}${team ? "&team=1" : ""}`,
  );
  const cells = useMemo(() => monthCells(view.jy, view.jm), [view]);
  const byDay = useMemo(
    () => itemsByDay(agenda.data?.items ?? [], window_.from, window_.to),
    [agenda.data, window_.from, window_.to],
  );
  const iso = todayIso();
  const selectedItems = byDay[selected] ?? [];
  const inMonth = selected >= window_.from && selected <= window_.to;

  function move(months: number) {
    const next = addJalaliMonths(view.jy, view.jm, months);
    setView(next);
    // Keep a day selected in the new month: today when it is there, else the 1st.
    const sameAsToday = next.jy === today.jy && next.jm === today.jm;
    setSelected(sameAsToday ? iso : jalaliToIso(next.jy, next.jm, 1));
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader
        title="تقویم"
        subtitle="مهلت‌ها، جلسه‌ها، ممیزی‌ها، بازنگری‌ها و مرخصی‌های شما در یک نگاه"
        actions={
          agenda.data?.is_lead ? (
            <label className="flex items-center gap-2 text-sm text-soft-foreground">
              <Switch checked={team} onChange={(event) => setTeam(event.target.checked)} aria-label="مرخصی تیم" />
              مرخصی تیم
            </label>
          ) : undefined
        }
      />

      <Card className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="sm" aria-label="ماه قبل" onClick={() => move(-1)}>
              <ChevronRight className="size-4" />
            </Button>
            <h2 className="min-w-[10rem] text-center text-lg font-bold text-foreground">
              {JALALI_MONTHS[view.jm - 1]} {toPersianDigits(view.jy)}
            </h2>
            <Button variant="ghost" size="sm" aria-label="ماه بعد" onClick={() => move(1)}>
              <ChevronLeft className="size-4" />
            </Button>
          </div>
          <Button
            size="sm"
            onClick={() => {
              setView({ jy: today.jy, jm: today.jm });
              setSelected(iso);
            }}
          >
            امروز
          </Button>
        </div>

        {agenda.error && !agenda.data ? <ErrorBanner message={agenda.error} /> : null}

        <div role="grid" aria-label="تقویم ماه" className="overflow-hidden rounded-xl border border-border">
          <div role="row" className="grid grid-cols-7 border-b border-border bg-muted/50 text-center text-xs text-muted-foreground">
            {JALALI_WEEKDAYS_SHORT.map((name, index) => (
              <div key={name} role="columnheader" className={cx("py-2", index === 6 && "text-destructive")}>
                {name}
              </div>
            ))}
          </div>
          <div className="grid grid-cols-7">
            {cells.map((cell, index) => {
              if (cell.day === null || cell.iso === null) {
                return <div key={index} role="gridcell" aria-hidden className="min-h-14 border-b border-e border-border bg-muted/20 sm:min-h-24" />;
              }
              const items = byDay[cell.iso] ?? [];
              const holiday = items.some((i) => i.kind === "holiday");
              const friday = index % 7 === 6;
              const isToday = cell.iso === iso;
              const isSelected = cell.iso === selected;
              return (
                <button
                  key={cell.iso}
                  type="button"
                  role="gridcell"
                  aria-selected={isSelected}
                  aria-label={`${formatJalali(cell.iso)}${items.length ? ` — ${toPersianDigits(items.length)} مورد` : ""}`}
                  onClick={() => setSelected(cell.iso!)}
                  className={cx(
                    "flex min-h-14 flex-col gap-1 border-b border-e border-border p-1.5 text-start transition-colors sm:min-h-24",
                    isSelected ? "bg-accent" : "hover:bg-accent/60",
                    (friday || holiday) && !isSelected && "bg-muted/30",
                  )}
                >
                  <span
                    className={cx(
                      "flex size-6 items-center justify-center rounded-full text-xs tabular-nums",
                      isToday ? "bg-primary font-bold text-primary-foreground" : friday || holiday ? "text-destructive" : "text-foreground",
                    )}
                  >
                    {toPersianDigits(cell.day)}
                  </span>
                  {/* A phone has no room for text: one dot per item (up to four). */}
                  <span className="flex flex-wrap gap-0.5 sm:hidden">
                    {items.slice(0, 4).map((item) => (
                      <span key={item.key} aria-hidden className={cx("size-1.5 rounded-full", AGENDA_TONE[item.kind].dot)} />
                    ))}
                  </span>
                  <span className="hidden min-w-0 flex-col gap-0.5 sm:flex">
                    {items.slice(0, CHIPS_PER_DAY).map((item) => (
                      <span key={item.key} className={cx("truncate rounded px-1 py-0.5 text-[11px] leading-4", AGENDA_TONE[item.kind].chip)}>
                        {item.title}
                      </span>
                    ))}
                    {items.length > CHIPS_PER_DAY && (
                      <span className="px-1 text-[11px] text-muted-foreground">+{toPersianDigits(items.length - CHIPS_PER_DAY)}</span>
                    )}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </Card>

      <Card aria-label="مواردِ روز انتخاب‌شده">
        <CardHeader title={inMonth ? formatJalali(selected) : "یک روز را انتخاب کنید"} icon={<CalendarRange />} />
        {selectedItems.length === 0 ? (
          <EmptyState compact icon={<CalendarRange />} message="در این روز موردی ندارید." />
        ) : (
          <ul className="divide-y divide-border">
            {selectedItems.map((item) => (
              <DayItem key={`${item.key}:${selected}`} item={item} />
            ))}
          </ul>
        )}
      </Card>

      <Legend />
    </div>
  );
}

function DayItem({ item }: { item: AgendaItem }) {
  const body = (
    <>
      <span aria-hidden className={cx("mt-2 size-2 shrink-0 rounded-full", AGENDA_TONE[item.kind].dot)} />
      <span className="min-w-0 flex-1">
        <span className="block font-medium text-foreground">{item.title}</span>
        <span className="block text-xs text-muted-foreground">
          {item.kind_label}
          {item.subtitle && ` · ${item.subtitle}`}
          {item.end_date && item.end_date !== item.date && ` · ${formatJalali(item.date)} تا ${formatJalali(item.end_date)}`}
        </span>
      </span>
      {item.overdue && <span className="shrink-0 rounded-full bg-rose-50 px-2 py-0.5 text-xs text-rose-800 dark:bg-rose-400/10 dark:text-rose-300">دیرکرد</span>}
    </>
  );
  return (
    <li>
      {item.url ? (
        <Link href={item.url} className="flex items-start gap-3 rounded-lg px-1 py-2.5 text-sm transition-colors hover:bg-accent">
          {body}
        </Link>
      ) : (
        <div className="flex items-start gap-3 px-1 py-2.5 text-sm">{body}</div>
      )}
    </li>
  );
}

const LEGEND: [keyof typeof AGENDA_TONE, string][] = [
  ["objective", "ریزهدف"],
  ["action", "اقدام اصلاحی"],
  ["meeting", "جلسه"],
  ["audit", "ممیزی"],
  ["risk_review", "بازنگری ریسک"],
  ["document_review", "بازنگری مستند"],
  ["leave", "مرخصی من"],
  ["team_leave", "مرخصی تیم"],
  ["delegation", "جانشینی"],
  ["holiday", "تعطیل رسمی"],
];

function Legend() {
  return (
    <ul aria-label="راهنمای رنگ‌ها" className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
      {LEGEND.map(([kind, label]) => (
        <li key={kind} className="flex items-center gap-1.5">
          <span aria-hidden className={cx("size-2 rounded-full", AGENDA_TONE[kind].dot)} />
          {label}
        </li>
      ))}
    </ul>
  );
}
