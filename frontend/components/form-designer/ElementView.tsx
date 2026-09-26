"use client";

import type { CSSProperties } from "react";
import { parseMarkers } from "@/lib/rich-text";
import { HEADING_SIZE_BONUS, LEADING } from "@/lib/form-layout";
import type { FormElement, HeadingProps } from "@/lib/form-designer";
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
  }
}
