"use client";

import { ChevronDown, ChevronUp, GripVertical, X } from "lucide-react";
import type { CSSProperties } from "react";
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
import { headingNumbers, type FormElement, type FormSettings } from "@/lib/form-designer";
import { useDragReorder } from "@/components/designer/useDragReorder";
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
  const drag = useDragReorder(onReorder);

  const pageStyle = {
    "--mm": `calc(100cqw / ${page.width})`,
    minHeight: mm(page.height),
    padding: `${mm(MARGIN_TOP)} ${mm(MARGIN_SIDE)} ${mm(MARGIN_BOTTOM)}`,
    fontSize: pt(settings.base_font_size),
  } as CSSProperties;

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200/80 bg-[radial-gradient(circle_at_1px_1px,rgb(148_163_184/0.35)_1px,transparent_0)] bg-[length:18px_18px] bg-slate-100 p-2 shadow-card sm:p-5">
      <div style={{ containerType: "inline-size" }} className={settings.orientation === "landscape" ? "" : "mx-auto max-w-[820px]"}>
        <div
          className="flex flex-col bg-white text-slate-950 shadow-[0_1px_3px_rgb(15_23_42/0.12),0_16px_40px_-16px_rgb(15_23_42/0.35)]"
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
              const marker = drag.marker(index);
              return (
                <div
                  key={element.key}
                  {...drag.rowProps(index)}
                  onClick={(event) => {
                    event.stopPropagation();
                    onSelect(element.key);
                  }}
                  className={`group relative -mx-[3px] rounded-sm px-[3px] outline-offset-2 ${
                    selected ? "outline outline-2 outline-brand-500" : "hover:outline hover:outline-1 hover:outline-brand-300"
                  } ${drag.isDragging(index) ? "opacity-40" : ""}`}
                >
                  {marker && (
                    <span
                      aria-hidden="true"
                      className={`absolute inset-x-0 h-0.5 bg-brand-500 shadow-[0_0_8px_rgb(14_165_233/0.6)] ${marker === "before" ? "-top-px" : "-bottom-px"}`}
                    />
                  )}
                  {!locked && (
                    <div
                      className={`absolute -top-3.5 start-0 z-10 items-center gap-0.5 rounded-lg border border-slate-200 bg-white p-0.5 text-xs shadow-raised animate-fade-in ${
                        selected ? "flex" : "hidden group-hover:flex"
                      }`}
                    >
                      <span
                        {...drag.gripProps(index, element.key)}
                        className="flex h-6 cursor-grab items-center px-0.5 text-slate-400 hover:text-slate-700 active:cursor-grabbing"
                      >
                        <GripVertical className="size-3.5" />
                      </span>
                      <ToolButton label="بالا" disabled={index === 0} onClick={() => onMove(index, -1)}>
                        <ChevronUp />
                      </ToolButton>
                      <ToolButton label="پایین" disabled={index === elements.length - 1} onClick={() => onMove(index, 1)}>
                        <ChevronDown />
                      </ToolButton>
                      <ToolButton label="حذف" danger onClick={() => onRemove(element.key)}>
                        <X />
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
  children: React.ReactNode;
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
      className={`flex size-6 items-center justify-center rounded-md transition-colors disabled:opacity-30 [&_svg]:size-3.5 ${danger ? "text-rose-600 hover:bg-rose-50" : "text-slate-600 hover:bg-slate-100"}`}
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

/** What the printed strip shows (backend `signoff.ROLES`, `form_renderer._approval_strip`): three plain
 *  columns, right to left — تهیه کننده | تایید کننده | تصویب کننده — each a stack of the role, سمت, name and
 *  signature. No table, no lines (owner's correction, 2026-10-01). The designer has nobody signing yet, so it
 *  shows the placeholders; on paper a done step prints its values alone. Every line is centred in its column, as
 *  on paper — except «امضا:», which the renderer draws at the column's right edge (`_SignatureCell`). */
const STRIP_ROLES = ["تهیه کننده", "تایید کننده", "تصویب کننده"];
/** The role titles sit four spaces right of the centre (backend `TITLE_SHIFT_SPACES`; a Vazir bold space is
 *  0.273 em wide), the سمت, name and signature stay put (owner's request, 2026-10-09). */
const TITLE_SHIFT = "1.09em";

function ApprovalStrip({ size }: { size: number }) {
  return (
    <div className="grid grid-cols-3" style={{ marginTop: mm(6), fontSize: pt(size) }}>
      {STRIP_ROLES.map((role) => (
        <div key={role} className="px-1">
          <div className="text-center font-bold" style={{ fontSize: pt(size + 1), height: mm(6), transform: `translateX(${TITLE_SHIFT})` }}>
            {role}:
          </div>
          {["سمت", "نام و نام خانوادگی"].map((label) => (
            <div key={label} className="text-center font-bold" style={{ height: mm(6) }}>
              {label} {role}:
            </div>
          ))}
          <div className="font-bold" style={{ height: mm(16), fontSize: pt(size - 1) }}>
            امضا:
          </div>
        </div>
      ))}
    </div>
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
