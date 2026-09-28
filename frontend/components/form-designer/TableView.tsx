"use client";

import { useRef, useState, type CSSProperties, type MouseEvent, type PointerEvent as ReactPointerEvent } from "react";
import {
  MAX_CELL,
  MIN_COLUMN_WIDTH,
  coveredCells,
  dragToDelta,
  evenWidths,
  mergeAt,
  mergeNext,
  mergeRange,
  moveBoundary,
  setCell,
  setColumnWidths,
  splitAt,
  type FormElement,
  type TableColumn,
  type TableProps,
} from "@/lib/form-designer";
import { LEADING } from "@/lib/form-layout";
import { RichText } from "./ElementView";
import { mm, pt } from "./units";

const LINE = "0.5pt solid #333";

function cellBorders(borders: TableProps["borders"], isLastHeader: boolean): CSSProperties {
  switch (borders) {
    case "all":
      return { border: LINE };
    case "horizontal":
      return { borderBottom: "0.4pt solid #333" };
    case "outer":
    case "none":
      return isLastHeader ? { borderBottom: "0.6pt solid #333" } : {};
  }
}

function BodyCell({ text, column, number }: { text: string; column: TableColumn; number: number }) {
  if (column.type === "row_number") return <>{text || number.toLocaleString("fa-IR")}</>;
  if (text.trim()) return <RichText text={text} />;
  if (column.type === "checkbox") {
    return <span className="inline-block align-middle" style={{ width: mm(3.4), height: mm(3.4), border: "0.6pt solid #333" }} />;
  }
  if (column.type === "date") return <span className="text-slate-400">/&nbsp;&nbsp;&nbsp;&nbsp;/</span>;
  return null;
}

/**
 * A table as it prints. While selected (`editing`), header and pre-written
 * cells are inputs, and each border between two columns can be dragged to
 * resize them (double-click evens all columns out).
 */
export function TableView({
  element,
  baseSize,
  editing,
  update,
}: {
  element: TableProps & { key: string };
  baseSize: number;
  editing: boolean;
  update: (updater: (element: FormElement) => FormElement) => void;
}) {
  const table = useRef<HTMLTableElement>(null);
  // The selected cell and, with Shift, the other corner of a range — grid rows
  // (header rows first, then written rows).
  const [picked, setActive] = useState<{ row: number; col: number } | null>(null);
  const [extent, setExtent] = useState<{ row: number; col: number } | null>(null);
  const [mergeError, setMergeError] = useState<string | null>(null);
  const covered = coveredCells(element.merges);
  const headerCount = element.header.length;
  // A selection left behind by removed rows or columns is no selection.
  const fits = (cell: { row: number; col: number } | null) =>
    cell !== null && cell.row < headerCount + element.rows.length && cell.col < element.columns.length;
  const active = fits(picked) ? picked : null;
  const size = element.font_size || baseSize - 1;
  const lastHeader = element.header.length - 1;
  const blank = Array.from({ length: element.blank_rows }, () => null);

  const edit = (updater: (t: TableProps) => TableProps) => update((current) => updater(current as TableProps & FormElement) as FormElement);

  function startResize(boundary: number, event: ReactPointerEvent<HTMLSpanElement>) {
    event.preventDefault();
    event.stopPropagation();
    const width = table.current?.getBoundingClientRect().width ?? 0;
    const startX = event.clientX;
    const start = element.columns.map((c) => c.width);
    const handle = event.currentTarget;
    handle.setPointerCapture(event.pointerId);
    const move = (moveEvent: PointerEvent) => {
      const widths = moveBoundary(start, boundary, dragToDelta(moveEvent.clientX - startX, width), MIN_COLUMN_WIDTH);
      edit((t) => setColumnWidths(t, widths));
    };
    const stop = () => {
      handle.removeEventListener("pointermove", move);
      handle.removeEventListener("pointerup", stop);
      handle.removeEventListener("pointercancel", stop);
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", stop);
    handle.addEventListener("pointercancel", stop);
  }

  const input = (value: string, onChange: (text: string) => void, align: string, bold = false, onPick?: (event: MouseEvent) => void) => (
    <input
      value={value}
      maxLength={MAX_CELL}
      onChange={(event) => onChange(event.target.value)}
      onClick={(event) => (onPick ? onPick(event) : event.stopPropagation())}
      className={`w-full min-w-0 bg-brand-50/60 outline-none ${bold ? "font-bold" : ""}`}
      style={{ textAlign: align as CSSProperties["textAlign"] }}
    />
  );

  function applyMerge(result: { table: TableProps; error?: string }) {
    setMergeError(result.error ?? null);
    if (!result.error) {
      edit(() => result.table);
      setExtent(null);
    }
  }

  function pick(row: number, col: number, event: MouseEvent) {
    event.stopPropagation();
    if (event.shiftKey && active) setExtent({ row, col });
    else {
      setActive({ row, col });
      setExtent(null);
    }
    setMergeError(null);
  }

  const inSelection = (row: number, col: number) => {
    if (!active) return false;
    const end = fits(extent) ? extent! : active;
    return (
      row >= Math.min(active.row, end.row) &&
      row <= Math.max(active.row, end.row) &&
      col >= Math.min(active.col, end.col) &&
      col <= Math.max(active.col, end.col)
    );
  };
  const activeMerge = active ? mergeAt(element.merges, active.row, active.col) : undefined;

  const spanOf = (row: number, col: number) => {
    const merge = element.merges.find((m) => m.row === row && m.col === col);
    return merge ? { rowSpan: merge.rowspan, colSpan: merge.colspan } : {};
  };

  let offset = 0;
  const boundaries = element.columns.slice(0, -1).map((column) => (offset += column.width));

  return (
    <div style={{ marginBottom: mm(2.5), fontSize: pt(size), lineHeight: 1.35 }}>
      {element.title.trim() && (
        <div className="font-bold" style={{ fontSize: pt(baseSize), lineHeight: LEADING, marginBottom: mm(1) }}>
          {element.title}
        </div>
      )}
      {editing && active && (
        <div
          className="mb-1 flex flex-wrap items-center gap-1 rounded-lg border border-brand-200 bg-brand-50 px-2 py-1 text-xs text-slate-700"
          onClick={(event) => event.stopPropagation()}
          style={{ fontSize: 12, lineHeight: 1.4 }}
        >
          <span className="font-bold">خانهٔ انتخاب‌شده:</span>
          {fits(extent) ? (
            <ToolbarButton onClick={() => applyMerge(mergeRange(element, active.row, active.col, extent!.row, extent!.col))}>ادغام خانه‌های انتخاب‌شده</ToolbarButton>
          ) : (
            <>
              <ToolbarButton onClick={() => applyMerge(mergeNext(element, active.row, active.col, "col"))}>ادغام با خانهٔ چپ</ToolbarButton>
              <ToolbarButton onClick={() => applyMerge(mergeNext(element, active.row, active.col, "row"))}>ادغام با خانهٔ پایین</ToolbarButton>
            </>
          )}
          {activeMerge && (
            <ToolbarButton
              onClick={() => {
                edit((t) => splitAt(t, active.row, active.col));
                setMergeError(null);
              }}
            >
              جدا کردن
            </ToolbarButton>
          )}
          <span className="text-slate-500">(Shift + کلیک: انتخاب چند خانه)</span>
          {mergeError && <span className="w-full text-rose-700">{mergeError}</span>}
        </div>
      )}
      <div className="relative">
        <table ref={table} className="w-full table-fixed border-collapse" style={element.borders === "outer" ? { border: "0.8pt solid #333" } : undefined}>
          <colgroup>
            {element.columns.map((column, i) => (
              <col key={i} style={{ width: `${column.width}%` }} />
            ))}
          </colgroup>
          <thead>
            {element.header.map((row, r) => (
              <tr
                key={r}
                style={{
                  height: mm(6),
                  background: element.header_shade ? "#e6e8ed" : undefined,
                  ...(element.borders === "horizontal" && r === 0 ? { borderTop: "0.6pt solid #333" } : {}),
                }}
              >
                {row.map((text, c) =>
                  covered.has(`${r},${c}`) ? null : (
                    <th
                      key={c}
                      {...spanOf(r, c)}
                      onClick={editing ? (event) => pick(r, c, event) : undefined}
                      className={`font-bold ${editing && inSelection(r, c) ? "outline outline-2 -outline-offset-2 outline-brand-400" : ""}`}
                      style={{ ...cellBorders(element.borders, r + (spanOf(r, c).rowSpan ?? 1) - 1 === lastHeader), padding: "2pt 3pt", textAlign: "center" }}
                    >
                      {editing
                        ? input(text, (next) => edit((t) => setCell(t, "header", r, c, next)), "center", true, (event) => pick(r, c, event))
                        : <RichText text={text} />}
                    </th>
                  ),
                )}
              </tr>
            ))}
          </thead>
          <tbody>
            {[...element.rows, ...blank].map((row, r) => (
              <tr key={r} style={{ height: mm(element.row_height) }}>
                {element.columns.map((column, c) => {
                  const g = headerCount + r;
                  if (row !== null && covered.has(`${g},${c}`)) return null;
                  const text = row ? row[c] : "";
                  const writable = editing && row !== null && column.type !== "row_number";
                  return (
                    <td
                      key={c}
                      {...(row !== null ? spanOf(g, c) : {})}
                      onClick={editing && row !== null ? (event) => pick(g, c, event) : undefined}
                      className={editing && row !== null && inSelection(g, c) ? "outline outline-2 -outline-offset-2 outline-brand-400" : undefined}
                      style={{
                        ...cellBorders(element.borders, false),
                        padding: "2pt 3pt",
                        textAlign: column.type === "text" ? column.align : "center",
                        verticalAlign: "middle",
                      }}
                    >
                      {writable
                        ? input(text, (next) => edit((t) => setCell(t, "rows", r, c, next)), column.align, false, (event) => pick(g, c, event))
                        : <BodyCell text={text} column={column} number={r + 1} />}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>

        {editing &&
          boundaries.map((at, i) => (
            <span
              key={i}
              role="separator"
              aria-orientation="vertical"
              aria-label={`تغییر پهنای ستون ${(i + 1).toLocaleString("fa-IR")} و ${(i + 2).toLocaleString("fa-IR")}`}
              title="برای تغییر پهنا بکشید؛ دوبار کلیک: پهنای برابر"
              onPointerDown={(event) => startResize(i, event)}
              onDoubleClick={(event) => {
                event.stopPropagation();
                edit((t) => setColumnWidths(t, evenWidths(t.columns.length)));
              }}
              onClick={(event) => event.stopPropagation()}
              className="group/handle absolute inset-y-0 z-10 flex w-3 cursor-col-resize touch-none justify-center"
              style={{ insetInlineStart: `calc(${at}% - 6px)` }}
            >
              <span className="w-0.5 bg-brand-400/0 group-hover/handle:bg-brand-500" />
            </span>
          ))}
      </div>
    </div>
  );
}

function ToolbarButton({ onClick, children }: { onClick: () => void; children: string }) {
  return (
    <button type="button" onClick={onClick} className="rounded-md border border-brand-300 bg-white px-2 py-0.5 text-brand-700 transition-colors hover:bg-brand-100">
      {children}
    </button>
  );
}
