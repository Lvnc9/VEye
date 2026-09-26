"use client";

import type { CSSProperties } from "react";
import { parseMarkers } from "@/lib/rich-text";
import {
  ANSWER_LINE,
  HEADING_SIZE_BONUS,
  LEADING,
  PHOTO_GAP,
  PHOTO_HEIGHT,
  PHOTO_WIDTH,
  SIGNATURE_GAP,
} from "@/lib/form-layout";
import type { FieldCell, FieldsProps, FormElement, HeadingProps } from "@/lib/form-designer";
import { mm, pt } from "./units";

const ALIGN: Record<string, CSSProperties["textAlign"]> = { right: "right", center: "center", left: "left" };

/** Text with the designer's inline markers, drawn as the PDF draws it. */
export function RichText({ text, inline = false }: { text: string; inline?: boolean }) {
  const runsOf = (line: string) =>
    parseMarkers(line).map((run, j) => (
      <span
        key={j}
        className={
          run.style === "bold" ? "font-bold" : run.style === "italic" ? "italic" : run.style === "underline" ? "underline" : ""
        }
      >
        {run.text}
      </span>
    ));
  if (inline) return <>{runsOf(text)}</>;
  return (
    <>
      {text.split("\n").map((line, i) => (
        <span key={i} className="block min-h-[1em]">
          {runsOf(line)}
        </span>
      ))}
    </>
  );
}

function headingBox(element: HeadingProps): CSSProperties {
  if (element.style === "band") {
    return { background: "#e6e8ed", border: "0.6pt solid #333", padding: `${mm(1.8)} ${mm(2)}` };
  }
  if (element.style === "underline") return { borderBottom: "0.9pt solid #333", padding: `${mm(0.6)} 0` };
  return { padding: `${mm(0.6)} 0` };
}

/**
 * One element as it will print. `editing` turns a heading's text into an input
 * in place (the selected element, when the form is editable).
 */
export function ElementView({
  element,
  baseSize,
  number,
  editing,
  onText,
}: {
  element: FormElement;
  baseSize: number;
  /** «2.1. » when the heading is numbered. */
  number?: string;
  editing: boolean;
  onText: (text: string) => void;
}) {
  switch (element.kind) {
    case "heading": {
      const size = baseSize + HEADING_SIZE_BONUS[element.level];
      return (
        <div style={{ marginTop: mm(2), marginBottom: mm(1.5) }}>
          <div
            className="font-bold"
            style={{ ...headingBox(element), fontSize: pt(size), lineHeight: LEADING, textAlign: ALIGN[element.align] }}
          >
            {editing ? (
              <span className="flex items-baseline gap-[0.3em]">
                {number && <span>{number}</span>}
                <input
                  value={element.text}
                  maxLength={300}
                  onChange={(event) => onText(event.target.value)}
                  onClick={(event) => event.stopPropagation()}
                  aria-label="متن عنوان"
                  className="w-full min-w-0 bg-transparent font-bold outline-none"
                  style={{ textAlign: ALIGN[element.align] }}
                />
              </span>
            ) : element.text.trim() ? (
              <>
                {number}
                <RichText text={element.text} inline />
              </>
            ) : (
              <span className="text-slate-400">عنوان خالی (چاپ نمی‌شود)</span>
            )}
          </div>
        </div>
      );
    }
    case "text": {
      const size = element.size || baseSize;
      return (
        <div
          style={{
            fontSize: pt(size),
            lineHeight: LEADING,
            textAlign: ALIGN[element.align],
            marginBottom: mm(1.5),
            ...(element.boxed ? { border: "0.6pt solid #333", padding: mm(3) } : {}),
          }}
        >
          {element.text.trim() ? (
            <RichText text={element.text} />
          ) : (
            <span className="text-slate-400">متن خالی (چاپ نمی‌شود)</span>
          )}
        </div>
      );
    }
    case "divider": {
      const width = element.style === "double" ? `${element.thickness * 2 + 1.6}pt` : `${element.thickness}pt`;
      return (
        <div style={{ paddingTop: mm(element.space_before), paddingBottom: mm(element.space_after) }}>
          <div style={{ borderTop: `${width} ${element.style} #333` }} />
        </div>
      );
    }
    case "spacer":
      return (
        <div
          className="flex items-center justify-center border border-dashed border-slate-300 text-[10px] text-slate-400"
          style={{ height: mm(element.height) }}
        >
          فاصله {element.height.toLocaleString("fa-IR")} میلی‌متر
        </div>
      );
    case "page_break":
      return (
        <div className="flex items-center gap-2 py-1 text-[10px] text-slate-500">
          <span className="h-px flex-1 border-t border-dashed border-slate-400" />
          شکست صفحه
          <span className="h-px flex-1 border-t border-dashed border-slate-400" />
        </div>
      );
    case "fields":
      return <FieldsView element={element} />;
    case "answer_box":
      return (
        <div style={{ marginBottom: mm(2) }}>
          {element.label.trim() && (
            <div className="font-bold" style={{ lineHeight: LEADING }}>
              {element.label}
            </div>
          )}
          <div
            className="flex flex-col"
            style={{
              height: element.lines ? mm(element.lines * ANSWER_LINE + 2) : mm(element.height),
              border: element.framed ? "0.6pt solid #333" : undefined,
              padding: element.framed ? `0 ${mm(3)}` : undefined,
            }}
          >
            {Array.from({ length: element.lines }, (_, i) => (
              <div
                key={i}
                className="shrink-0"
                style={{ height: mm(ANSWER_LINE), borderBottom: `0.4pt ${element.line_style} #333` }}
              />
            ))}
          </div>
        </div>
      );
    case "signatures": {
      const boxes = [
        ...element.boxes,
        ...(element.stamp ? [{ caption: "محل مهر", name_line: false, date_line: false }] : []),
      ];
      return (
        <div className="flex" style={{ gap: mm(SIGNATURE_GAP), marginTop: mm(3), marginBottom: mm(2), fontSize: "0.9em" }}>
          {boxes.map((box, i) => (
            <div key={i} className="min-w-0 flex-1" style={{ height: mm(element.height), border: "0.6pt solid #333", padding: mm(2) }}>
              <div className="truncate text-center font-bold">{box.caption}</div>
              {box.name_line && <BlankLine label="نام و نام خانوادگی:" />}
              {box.date_line && <BlankLine label="تاریخ:" />}
            </div>
          ))}
        </div>
      );
    }
  }
}

function BlankLine({ label, style = "dotted" }: { label: string; style?: string }) {
  return (
    <div className="flex items-end gap-1" style={{ marginTop: mm(1.5) }}>
      <span className="shrink-0">{label}</span>
      <span className="flex-1" style={{ borderBottom: `0.5pt ${style} #333`, marginBottom: "0.3em" }} />
    </div>
  );
}

function DigitBoxes({ count }: { count: number }) {
  return (
    <span className="flex" dir="ltr">
      {Array.from({ length: count }, (_, i) => (
        <span key={i} className="-ms-[0.5pt] inline-block" style={{ width: mm(5), height: mm(5), border: "0.5pt solid #333" }} />
      ))}
    </span>
  );
}

function FieldCellView({ cell, blank }: { cell: FieldCell; blank: FieldsProps["blank"] }) {
  const label = cell.label.trim();
  if (cell.type === "checkbox") {
    return (
      <span className="flex items-center" style={{ gap: mm(1.5) }}>
        <span className="inline-block shrink-0" style={{ width: mm(3.4), height: mm(3.4), border: "0.6pt solid #333" }} />
        {label}
      </span>
    );
  }
  const line = blank === "box" ? { border: "0.5pt solid #333", height: mm(5.6) } : { borderBottom: `0.5pt ${blank === "dotted" ? "dotted" : "solid"} #333` };
  return (
    <span className="flex min-w-0 items-end" style={{ gap: mm(1.5) }}>
      {label && <span className="shrink-0 whitespace-nowrap">{label}:</span>}
      {cell.type === "national_code" || cell.type === "phone" ? (
        <DigitBoxes count={cell.type === "national_code" ? 10 : 11} />
      ) : cell.type === "date" ? (
        <span className="flex flex-1 items-end" style={{ gap: mm(1) }} dir="ltr">
          {[0, 1, 2].map((part) => (
            <span key={part} className="flex flex-1 items-end" style={{ gap: mm(1) }}>
              {part > 0 && <span>/</span>}
              <span className="flex-1" style={{ borderBottom: `0.5pt ${blank === "underline" ? "solid" : "dotted"} #333`, marginBottom: "0.3em" }} />
            </span>
          ))}
        </span>
      ) : (
        <span className="flex-1" style={{ ...line, minWidth: mm(3), marginBottom: "0.3em" }} />
      )}
    </span>
  );
}

function FieldsView({ element }: { element: FieldsProps }) {
  return (
    <div className="flex" style={{ gap: element.photo ? mm(PHOTO_GAP) : 0, marginBottom: mm(1.5) }}>
      <div className="min-w-0 flex-1">
        {element.rows.map((row, r) => (
          <div key={r} className="flex items-end" style={{ height: mm(element.row_height), paddingBottom: mm(element.row_height * 0.2) }}>
            {row.cells.map((cell, c) => (
              <div key={c} className="min-w-0" style={{ width: `${cell.width}%`, padding: `0 ${mm(1)} 0 ${mm(1.5)}` }}>
                <FieldCellView cell={cell} blank={element.blank} />
              </div>
            ))}
          </div>
        ))}
      </div>
      {element.photo && (
        <div
          className="flex shrink-0 flex-col items-center justify-center text-center text-slate-500"
          style={{ width: mm(PHOTO_WIDTH), height: mm(PHOTO_HEIGHT), border: "0.6pt solid #333", fontSize: "0.8em" }}
        >
          <span>محل الصاق عکس</span>
          <span>ابعاد ۳ در ۴</span>
        </div>
      )}
    </div>
  );
}
