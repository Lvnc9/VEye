"use client";

import { useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import { useReducedMotion } from "motion/react";
import { NumberTicker } from "./NumberTicker";
import { cx } from "./cx";

export interface DonutSlice {
  key: string;
  label: string;
  value: number;
  /** A CSS colour, e.g. `var(--color-emerald-500)`. */
  color: string;
}

const FORMAT = new Intl.NumberFormat("fa-IR");

/**
 * A ring of parts with the total in its middle and a legend beside it (recharts; load it with
 * next/dynamic so the chart library only reaches pages that draw one). Hovering a slice — or its legend
 * row — dims the others. Persian digits; the legend is the accessible text, the ring is decorative.
 */
export default function DonutChart({
  data,
  totalLabel,
  className,
}: {
  data: DonutSlice[];
  totalLabel: string;
  className?: string;
}) {
  const [active, setActive] = useState<number | null>(null);
  const reduce = useReducedMotion();
  const total = data.reduce((sum, slice) => sum + slice.value, 0);
  const shown = data.filter((slice) => slice.value > 0);

  return (
    // Laid out by its own width (a container query), not the window's: in a narrow card the legend goes
    // under the ring, in a wide one beside it.
    <div className={cx("@container", className)}>
    <div className="flex flex-col items-center gap-5 @md:flex-row">
      <div className="relative size-44 shrink-0" aria-hidden>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={shown.length ? shown : [{ key: "none", label: "", value: 1, color: "var(--muted)" }]}
              dataKey="value"
              nameKey="label"
              innerRadius="68%"
              outerRadius="96%"
              paddingAngle={shown.length > 1 ? 3 : 0}
              cornerRadius={6}
              stroke="none"
              startAngle={90}
              endAngle={-270}
              isAnimationActive={!reduce}
              animationDuration={900}
              onMouseEnter={(_, index) => setActive(index)}
              onMouseLeave={() => setActive(null)}
            >
              {(shown.length ? shown : [{ key: "none", color: "var(--muted)" }]).map((slice, index) => (
                <Cell
                  key={slice.key}
                  fill={slice.color}
                  fillOpacity={active === null || active === index ? 1 : 0.3}
                  style={{ transition: "fill-opacity 200ms ease-out", outline: "none" }}
                />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-black leading-9 text-foreground">
            <NumberTicker value={total} />
          </span>
          <span className="text-xs text-muted-foreground">{totalLabel}</span>
        </div>
      </div>

      <ul className="w-full min-w-0 flex-1 space-y-1">
        {data.map((slice) => {
          const index = shown.findIndex((s) => s.key === slice.key);
          const share = total ? Math.round((slice.value / total) * 100) : 0;
          return (
            <li
              key={slice.key}
              onMouseEnter={() => index >= 0 && setActive(index)}
              onMouseLeave={() => setActive(null)}
              className={cx(
                "flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm transition-colors",
                index >= 0 && active === index && "bg-accent",
              )}
            >
              <span aria-hidden className="size-2.5 shrink-0 rounded-full" style={{ backgroundColor: slice.color }} />
              <span className="min-w-0 flex-1 truncate text-soft-foreground">{slice.label}</span>
              <span className="text-xs text-muted-foreground tabular-nums">{FORMAT.format(share)}٪</span>
              <span className="w-8 text-start font-bold text-foreground tabular-nums">{FORMAT.format(slice.value)}</span>
            </li>
          );
        })}
      </ul>
    </div>
    </div>
  );
}
