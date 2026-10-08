"use client";

import { toPersianDigits } from "@/lib/jalali";
import { IMPACT_LABELS, LIKELIHOOD_LABELS, RISK_LEVEL_LABELS, RISK_LEVEL_STYLE, matrixRows, type RiskMatrix } from "@/lib/quality";
import { cx } from "@/components/ui/cx";

/**
 * The 5×5 heat map: likelihood up the side (most likely on top), impact along the bottom, each cell in its
 * level's colour with how many risks sit in it. Every number is the server's (`/quality/risks/matrix/`);
 * clicking a cell asks the page to filter the register to it, clicking it again lets go. A cell with no risk
 * is still a button (so the grid's rhythm holds) but says «۰» quietly. Fits a 375 px phone: six 2.75rem
 * columns.
 */
export function RiskHeatMap({
  matrix,
  selected,
  onSelect,
}: {
  matrix: RiskMatrix;
  selected: { likelihood: number; impact: number } | null;
  onSelect: (cell: { likelihood: number; impact: number } | null) => void;
}) {
  const rows = matrixRows(matrix.cells);
  return (
    <div className="space-y-3">
      <div className="flex items-stretch gap-2" dir="ltr">
        {/* The likelihood axis, written upwards. */}
        <div className="flex w-5 shrink-0 items-center justify-center">
          <span className="-rotate-90 whitespace-nowrap text-xs font-bold text-slate-500" dir="rtl">
            احتمال ↑
          </span>
        </div>
        <div className="grid flex-1 grid-cols-[2.25rem_repeat(5,minmax(0,1fr))] gap-1.5">
          {rows.map((row) => (
            <div key={row[0].likelihood} className="contents">
              <span className="flex items-center justify-center text-xs text-slate-500" title={LIKELIHOOD_LABELS[row[0].likelihood]}>
                {toPersianDigits(row[0].likelihood)}
              </span>
              {row.map((cell) => {
                const isSelected = selected?.likelihood === cell.likelihood && selected?.impact === cell.impact;
                return (
                  <button
                    key={cell.impact}
                    type="button"
                    aria-pressed={isSelected}
                    aria-label={`احتمال ${toPersianDigits(cell.likelihood)}، اثر ${toPersianDigits(cell.impact)} (${RISK_LEVEL_LABELS[cell.level]}): ${toPersianDigits(cell.count)} ریسک`}
                    onClick={() => onSelect(isSelected ? null : { likelihood: cell.likelihood, impact: cell.impact })}
                    className={cx(
                      "flex aspect-square min-h-11 items-center justify-center rounded-lg text-sm transition",
                      RISK_LEVEL_STYLE[cell.level].cell,
                      cell.count > 0 ? "font-bold" : "opacity-60",
                      isSelected ? "ring-2 ring-slate-900 ring-offset-2" : "hover:brightness-95",
                    )}
                  >
                    {toPersianDigits(cell.count)}
                  </button>
                );
              })}
            </div>
          ))}
          <span />
          {[1, 2, 3, 4, 5].map((impact) => (
            <span key={impact} className="text-center text-xs text-slate-500" title={IMPACT_LABELS[impact]}>
              {toPersianDigits(impact)}
            </span>
          ))}
        </div>
      </div>
      <p className="text-center text-xs font-bold text-slate-500">اثر →</p>
      <ul className="flex flex-wrap justify-center gap-x-3 gap-y-1.5 text-xs text-slate-600">
        {(Object.keys(RISK_LEVEL_LABELS) as (keyof typeof RISK_LEVEL_LABELS)[]).map((level) => (
          <li key={level} className="inline-flex items-center gap-1.5">
            <span aria-hidden className={cx("size-3 rounded", RISK_LEVEL_STYLE[level].cell)} />
            {RISK_LEVEL_LABELS[level]}: {toPersianDigits(matrix.levels[level])}
          </li>
        ))}
      </ul>
    </div>
  );
}
