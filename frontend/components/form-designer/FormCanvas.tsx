"use client";

import { useRef, useState, type CSSProperties, type DragEvent } from "react";
import {
  FOOTER_HEIGHT,
  HEADER_GAP,
  HEADER_HEIGHT,
  LOGO_CELL,
  MARGIN_BOTTOM,
  MARGIN_SIDE,
  MARGIN_TOP,
  META_CELL,
  PAGE,
} from "@/lib/form-layout";
import { dropIndex, headingNumbers, type FormElement, type FormSettings } from "@/lib/form-designer";
import { ElementView } from "./ElementView";
import { mm, pt } from "./units";

export interface CanvasHeader {
  title: string;
  fullCode: string;
  revision: string;
  date: string;
  companyName: string;
  logoUrl: string | null;
  footnote1: string;
  footnote2: string;
}

/**
 * The form drawn on an A4 page, the way the PDF prints it: header band, the
 * elements, the footer. The page grows with its content instead of paginating;
 * «نمایش» (the preview PDF) shows the real pages.
 */
export function FormCanvas({
  header,
  settings,
  elements,
  selectedKey,
  locked,
  onSelect,
  onMove,
  onRemove,
  onReorder,
  onUpdate,
}: {
  header: CanvasHeader;
  settings: FormSettings;
  elements: FormElement[];
  selectedKey: string | null;
  locked: boolean;
  onSelect: (key: string | null) => void;
  onMove: (index: number, direction: -1 | 1) => void;
  onRemove: (key: string) => void;
  onReorder: (from: number, to: number) => void;
  /** Edits made on the canvas itself (heading text, table cells, column widths). */
  onUpdate: (key: string, updater: (element: FormElement) => FormElement) => void;
}) {
  const page = PAGE[settings.orientation];
  const numbers = headingNumbers(elements);
  const [dragFrom, setDragFrom] = useState<number | null>(null);
  const [dropAt, setDropAt] = useState<{ index: number; after: boolean } | null>(null);
  const rows = useRef<(HTMLDivElement | null)[]>([]);

  function dragOver(event: DragEvent, index: number) {
    if (dragFrom === null) return;
    event.preventDefault();
    const box = event.currentTarget.getBoundingClientRect();
    const after = event.clientY > box.top + box.height / 2;
    if (dropAt?.index !== index || dropAt.after !== after) setDropAt({ index, after });
  }

  function drop(event: DragEvent) {
    event.preventDefault();
    if (dragFrom !== null && dropAt) onReorder(dragFrom, dropIndex(dragFrom, dropAt.index, dropAt.after));
    setDragFrom(null);
    setDropAt(null);
  }

  const pageStyle = {
    "--mm": `calc(100cqw / ${page.width})`,
    minHeight: mm(page.height),
    padding: `${mm(MARGIN_TOP)} ${mm(MARGIN_SIDE)} ${mm(MARGIN_BOTTOM)}`,
    fontSize: pt(settings.base_font_size),
  } as CSSProperties;

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-slate-100 p-2 sm:p-4">
      <div style={{ containerType: "inline-size" }} className={settings.orientation === "landscape" ? "" : "mx-auto max-w-[820px]"}>
        <div
          className="flex flex-col bg-white text-slate-950 shadow-md"
          style={pageStyle}
          onClick={() => onSelect(null)}
        >
          <HeaderBand header={header} settings={settings} />

          <div className="flex-1" style={{ paddingTop: mm(HEADER_GAP) }}>
            {settings.header.show_letter_box && <LetterBox />}

            {elements.length === 0 && (
              <p className="py-10 text-center text-sm text-slate-400">
                {locked ? "این فرم هنوز جزئی ندارد." : "از نوار «افزودن» بالای صفحه یک جزء به فرم اضافه کنید."}
              </p>
            )}

            {elements.map((element, index) => {
              const selected = element.key === selectedKey;
              const marker = dropAt?.index === index ? (dropAt.after ? "after" : "before") : null;
              return (
                <div
                  key={element.key}
                  ref={(node) => {
                    rows.current[index] = node;
                  }}
                  onClick={(event) => {
                    event.stopPropagation();
                    onSelect(element.key);
                  }}
                  onDragOver={(event) => dragOver(event, index)}
                  onDrop={drop}
                  className={`group relative -mx-[3px] rounded-sm px-[3px] outline-offset-2 ${
                    selected ? "outline outline-2 outline-indigo-500" : "hover:outline hover:outline-1 hover:outline-indigo-200"
                  } ${dragFrom === index ? "opacity-40" : ""}`}
                >
                  {marker && (
                    <span
                      aria-hidden="true"
                      className={`absolute inset-x-0 h-0.5 bg-indigo-500 ${marker === "before" ? "-top-px" : "-bottom-px"}`}
                    />
                  )}
                  {!locked && (
                    <div
                      className={`absolute -top-3 start-0 z-10 items-center gap-0.5 rounded border border-slate-200 bg-white px-0.5 text-xs shadow-sm ${
                        selected ? "flex" : "hidden group-hover:flex"
                      }`}
                    >
                      <span
                        draggable
                        onDragStart={(event) => {
                          event.dataTransfer.effectAllowed = "move";
                          event.dataTransfer.setData("text/plain", element.key); // Firefox needs data to start a drag
                          const row = rows.current[index];
                          if (row) event.dataTransfer.setDragImage(row, 16, 16);
                          setDragFrom(index);
                        }}
                        onDragEnd={() => {
                          setDragFrom(null);
                          setDropAt(null);
                        }}
                        title="برای جابه‌جایی بکشید"
                        className="cursor-grab px-1 text-slate-500 active:cursor-grabbing"
                      >
                        ⠿
                      </span>
                      <ToolButton label="بالا" disabled={index === 0} onClick={() => onMove(index, -1)}>
                        ↑
                      </ToolButton>
                      <ToolButton label="پایین" disabled={index === elements.length - 1} onClick={() => onMove(index, 1)}>
                        ↓
                      </ToolButton>
                      <ToolButton label="حذف" danger onClick={() => onRemove(element.key)}>
                        ✕
                      </ToolButton>
                    </div>
                  )}
                  <ElementView
                    element={element}
                    baseSize={settings.base_font_size}
                    number={numbers.get(element.key)}
                    editing={selected && !locked}
                    update={(updater) => onUpdate(element.key, updater)}
                  />
                </div>
              );
            })}

            {settings.approval_strip && <ApprovalStrip size={settings.base_font_size - 1} />}
          </div>

          <Footer header={header} />
        </div>
      </div>
    </div>
  );
}

function ToolButton({
  label,
  disabled,
  danger,
  onClick,
  children,
}: {
  label: string;
  disabled?: boolean;
  danger?: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={(event) => {
        event.stopPropagation();
        onClick();
      }}
      className={`h-6 min-w-6 rounded px-1 disabled:opacity-30 ${danger ? "text-red-600 hover:bg-red-50" : "text-slate-600 hover:bg-slate-100"}`}
    >
      {children}
    </button>
  );
}

function HeaderBand({ header, settings }: { header: CanvasHeader; settings: FormSettings }) {
  const meta = [`کد: ${header.fullCode}`, `بازنگری: ${header.revision}`, `تاریخ: ${header.date}`, "صفحه ۱ از ۱"];
  return (
    <div className="flex border-[0.8pt] border-slate-800" style={{ height: mm(HEADER_HEIGHT) }}>
      <div className="flex shrink-0 items-center justify-center border-e-[0.5pt] border-slate-800" style={{ width: mm(LOGO_CELL) }}>
        {header.logoUrl && (
          // eslint-disable-next-line @next/next/no-img-element -- an authenticated API image
          <img src={header.logoUrl} alt="لوگو" className="object-contain" style={{ width: mm(19), height: mm(19) }} />
        )}
      </div>
      <div className="flex min-w-0 flex-1 flex-col items-center justify-center px-2 text-center" style={{ lineHeight: 1.45 }}>
        {settings.header.show_company_name && header.companyName && (
          <span className="text-slate-500" style={{ fontSize: pt(9) }}>
            {header.companyName}
          </span>
        )}
        <span className="font-bold" style={{ fontSize: pt(13) }}>
          {header.title}
        </span>
        {settings.header.subtitle && (
          <span className="text-slate-500" style={{ fontSize: pt(8.5) }}>
            {settings.header.subtitle}
          </span>
        )}
      </div>
      <div className="flex shrink-0 flex-col border-s-[0.5pt] border-slate-800" style={{ width: mm(META_CELL), fontSize: pt(8.5) }}>
        {meta.map((line, i) => (
          <span key={i} className={`flex flex-1 items-center px-[0.5em] ${i ? "border-t-[0.3pt] border-slate-300" : ""}`}>
            {line}
          </span>
        ))}
      </div>
    </div>
  );
}

function LetterBox() {
  return (
    <div className="flex flex-col items-end" style={{ marginBottom: mm(1), fontSize: "0.9em" }}>
      {["شماره:", "تاریخ:", "پیوست:"].map((label) => (
        <span key={label} className="flex items-baseline gap-1" style={{ lineHeight: 1.9 }}>
          {label}
          <span className="inline-block border-b border-dotted border-slate-500" style={{ width: mm(30) }} />
        </span>
      ))}
    </div>
  );
}

function ApprovalStrip({ size }: { size: number }) {
  return (
    <table className="w-full table-fixed border-collapse text-center" style={{ marginTop: mm(6), fontSize: pt(size) }}>
      <tbody>
        <tr className="bg-[#e6e8ed] font-bold">
          {["تدوین کننده", "تایید کننده", "تصویب کننده"].map((role) => (
            <td key={role} className="border-[0.5pt] border-slate-700 py-0.5">
              {role}
            </td>
          ))}
        </tr>
        {[0, 1, 2].map((row) => (
          <tr key={row}>
            {[0, 1, 2].map((cell) => (
              <td key={cell} className="border-[0.5pt] border-slate-700" style={{ height: row === 2 ? mm(14) : mm(5) }} />
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Footer({ header }: { header: CanvasHeader }) {
  return (
    <div className="flex items-end justify-between border-t-[0.6pt] border-slate-800" style={{ height: mm(FOOTER_HEIGHT), marginTop: mm(3) }}>
      <div className="self-start text-slate-500" style={{ paddingTop: mm(2), lineHeight: 1.6 }}>
        {header.footnote1 && <div style={{ fontSize: pt(9) }}>{header.footnote1}</div>}
        {header.footnote2 && <div style={{ fontSize: pt(8) }}>{header.footnote2}</div>}
      </div>
      <div
        className="flex items-center justify-center border border-dashed border-slate-300 text-[8px] text-slate-400"
        style={{ width: mm(FOOTER_HEIGHT - 2), height: mm(FOOTER_HEIGHT - 2) }}
      >
        QR
      </div>
    </div>
  );
}
