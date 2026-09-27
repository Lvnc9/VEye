"use client";

import { useRef, type CSSProperties, type PointerEvent as ReactPointerEvent } from "react";
import {
  MAX_CELL,
  MIN_COLUMN_WIDTH,
  dragToDelta,
  evenWidths,
  moveBoundary,
  setCell,
  setColumnWidths,
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

  const input = (value: string, onChange: (text: string) => void, align: string, bold = false) => (
    <input
      value={value}
      maxLength={MAX_CELL}
      onChange={(event) => onChange(event.target.value)}
      onClick={(event) => event.stopPropagation()}
      className={`w-full min-w-0 bg-indigo-50/60 outline-none ${bold ? "font-bold" : ""}`}
      style={{ textAlign: align as CSSProperties["textAlign"] }}
    />
  );

  let offset = 0;
  const boundaries = element.columns.slice(0, -1).map((column) => (offset += column.width));

  return (
    <div style={{ marginBottom: mm(2.5), fontSize: pt(size), lineHeight: 1.35 }}>
      {element.title.trim() && (
        <div className="font-bold" style={{ fontSize: pt(baseSize), lineHeight: LEADING, marginBottom: mm(1) }}>
          {element.title}
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
                {row.map((text, c) => (
                  <th key={c} className="font-bold" style={{ ...cellBorders(element.borders, r === lastHeader), padding: "2pt 3pt", textAlign: "center" }}>
                    {editing ? input(text, (next) => edit((t) => setCell(t, "header", r, c, next)), "center", true) : <RichText text={text} />}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {[...element.rows, ...blank].map((row, r) => (
              <tr key={r} style={{ height: mm(element.row_height) }}>
                {element.columns.map((column, c) => {
                  const text = row ? row[c] : "";
                  const writable = editing && row !== null && column.type !== "row_number";
                  return (
                    <td
                      key={c}
                      style={{
                        ...cellBorders(element.borders, false),
                        padding: "2pt 3pt",
                        textAlign: column.type === "text" ? column.align : "center",
                        verticalAlign: "middle",
                      }}
                    >
                      {writable
                        ? input(text, (next) => edit((t) => setCell(t, "rows", r, c, next)), column.align)
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
              <span className="w-0.5 bg-indigo-400/0 group-hover/handle:bg-indigo-500" />
            </span>
          ))}
      </div>
    </div>
  );
}
