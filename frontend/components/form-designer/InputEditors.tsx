"use client";

import {
  FIELD_TYPE_LABELS,
  MAX_FIELDS_PER_ROW,
  MAX_FIELD_ROWS,
  MAX_LABEL,
  MAX_SIGNATURE_BOXES,
  MIN_FIELD_WIDTH,
  evenWidths,
  moveElement,
  setWidth,
  type AnswerBoxProps,
  type FieldCell,
  type FieldType,
  type FieldsProps,
  type SignaturesProps,
} from "@/lib/form-designer";
import { inputClass } from "@/components/designer/ui";
import { Check, Field, NumberInput, Select } from "./Inspector";

type Patch<T> = (patch: Partial<T>) => void;

const smallButton =
  "rounded border border-slate-300 bg-white px-2 py-0.5 text-xs text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40";

function withWidths(cells: FieldCell[], widths: number[]): FieldCell[] {
  return cells.map((cell, i) => ({ ...cell, width: widths[i] }));
}

export function FieldsEditor({ element, disabled, set }: { element: FieldsProps; disabled: boolean; set: Patch<FieldsProps> }) {
  const setRow = (r: number, cells: FieldCell[]) =>
    set({ rows: element.rows.map((row, i) => (i === r ? { cells } : row)) });

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <Field label="شکل جای خالی">
          <Select
            value={element.blank}
            disabled={disabled}
            options={[
              ["underline", "خط ممتد"],
              ["dotted", "نقطه‌چین"],
              ["box", "کادر"],
            ]}
            onChange={(blank) => set({ blank })}
          />
        </Field>
        <Field label="ارتفاع ردیف (میلی‌متر)">
          <NumberInput value={element.row_height} min={6} max={20} disabled={disabled} onChange={(row_height) => set({ row_height })} />
        </Field>
      </div>
      <Check label="کادر عکس ۳×۴ در کنار فیلدها" checked={element.photo} disabled={disabled} onChange={(photo) => set({ photo })} />

      <div className="space-y-3">
        {element.rows.map((row, r) => (
          <fieldset key={r} className="space-y-2 rounded border border-slate-200 p-2">
            <legend className="flex w-full items-center gap-1 px-1 text-xs font-medium text-slate-600">
              <span className="flex-1">ردیف {(r + 1).toLocaleString("fa-IR")}</span>
              <button type="button" className={smallButton} disabled={disabled || r === 0} aria-label="ردیف بالا" onClick={() => set({ rows: moveElement(element.rows, r, r - 1) })}>
                ↑
              </button>
              <button
                type="button"
                className={smallButton}
                disabled={disabled || r === element.rows.length - 1}
                aria-label="ردیف پایین"
                onClick={() => set({ rows: moveElement(element.rows, r, r + 1) })}
              >
                ↓
              </button>
              <button
                type="button"
                className={`${smallButton} text-red-600`}
                disabled={disabled || element.rows.length === 1}
                aria-label="حذف ردیف"
                onClick={() => set({ rows: element.rows.filter((_, i) => i !== r) })}
              >
                ✕
              </button>
            </legend>
            {row.cells.map((cell, c) => (
              <div key={c} className="space-y-1 border-b border-slate-100 pb-2 last:border-0 last:pb-0">
                <div className="flex gap-1">
                  <input
                    value={cell.label}
                    maxLength={MAX_LABEL}
                    disabled={disabled}
                    aria-label="برچسب"
                    placeholder="برچسب (مثلاً نام پدر)"
                    onChange={(event) => setRow(r, row.cells.map((x, i) => (i === c ? { ...x, label: event.target.value } : x)))}
                    className={`${inputClass} py-1`}
                  />
                  <button
                    type="button"
                    className={`${smallButton} text-red-600`}
                    disabled={disabled || row.cells.length === 1}
                    aria-label="حذف خانه"
                    onClick={() => {
                      const cells = row.cells.filter((_, i) => i !== c);
                      setRow(r, withWidths(cells, evenWidths(cells.length)));
                    }}
                  >
                    ✕
                  </button>
                </div>
                <div className="grid grid-cols-[1fr_5.5rem] gap-1">
                  <Select<FieldType>
                    value={cell.type}
                    disabled={disabled}
                    options={Object.entries(FIELD_TYPE_LABELS) as [FieldType, string][]}
                    onChange={(type) => setRow(r, row.cells.map((x, i) => (i === c ? { ...x, type } : x)))}
                  />
                  <NumberInput
                    value={cell.width}
                    min={MIN_FIELD_WIDTH}
                    max={100}
                    disabled={disabled || row.cells.length === 1}
                    onChange={(width) =>
                      setRow(r, withWidths(row.cells, setWidth(row.cells.map((x) => x.width), c, width, MIN_FIELD_WIDTH)))
                    }
                  />
                </div>
              </div>
            ))}
            <div className="flex flex-wrap gap-1">
              <button
                type="button"
                className={smallButton}
                disabled={disabled || row.cells.length >= MAX_FIELDS_PER_ROW}
                onClick={() => {
                  const cells: FieldCell[] = [...row.cells, { label: "", type: "text", width: 0 }];
                  setRow(r, withWidths(cells, evenWidths(cells.length)));
                }}
              >
                + خانه
              </button>
              <button type="button" className={smallButton} disabled={disabled} onClick={() => setRow(r, withWidths(row.cells, evenWidths(row.cells.length)))}>
                پهنای برابر
              </button>
            </div>
          </fieldset>
        ))}
        <button
          type="button"
          className={smallButton}
          disabled={disabled || element.rows.length >= MAX_FIELD_ROWS}
          onClick={() => set({ rows: [...element.rows, { cells: [{ label: "", type: "text", width: 100 }] }] })}
        >
          + ردیف
        </button>
        <p className="text-xs text-slate-500">پهنای هر خانه درصدی از ردیف است و جمع هر ردیف ۱۰۰ می‌شود.</p>
      </div>
    </div>
  );
}

export function AnswerBoxEditor({ element, disabled, set }: { element: AnswerBoxProps; disabled: boolean; set: Patch<AnswerBoxProps> }) {
  return (
    <div className="space-y-4">
      <Field label="عنوان (اختیاری)">
        <input
          value={element.label}
          maxLength={MAX_LABEL}
          disabled={disabled}
          placeholder="مثال: توضیحات"
          onChange={(event) => set({ label: event.target.value })}
          className={inputClass}
        />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="تعداد خط">
          <NumberInput value={element.lines} min={0} max={25} disabled={disabled} onChange={(lines) => set({ lines })} />
        </Field>
        <Field label="نوع خط">
          <Select
            value={element.line_style}
            disabled={disabled || element.lines === 0}
            options={[
              ["dotted", "نقطه‌چین"],
              ["solid", "ممتد"],
            ]}
            onChange={(line_style) => set({ line_style })}
          />
        </Field>
      </div>
      {element.lines === 0 && (
        <Field label="ارتفاع کادر (میلی‌متر)">
          <NumberInput value={element.height} min={10} max={200} disabled={disabled} onChange={(height) => set({ height })} />
        </Field>
      )}
      <Check label="با قاب" checked={element.framed} disabled={disabled} onChange={(framed) => set({ framed })} />
    </div>
  );
}

export function SignaturesEditor({ element, disabled, set }: { element: SignaturesProps; disabled: boolean; set: Patch<SignaturesProps> }) {
  const setBox = (b: number, patch: Partial<SignaturesProps["boxes"][number]>) =>
    set({ boxes: element.boxes.map((box, i) => (i === b ? { ...box, ...patch } : box)) });
  return (
    <div className="space-y-4">
      {element.boxes.map((box, b) => (
        <fieldset key={b} className="space-y-2 rounded border border-slate-200 p-2">
          <div className="flex gap-1">
            <input
              value={box.caption}
              maxLength={MAX_LABEL}
              disabled={disabled}
              aria-label="عنوان کادر"
              onChange={(event) => setBox(b, { caption: event.target.value })}
              className={`${inputClass} py-1`}
            />
            <button
              type="button"
              className={`${smallButton} text-red-600`}
              disabled={disabled || element.boxes.length === 1}
              aria-label="حذف کادر"
              onClick={() => set({ boxes: element.boxes.filter((_, i) => i !== b) })}
            >
              ✕
            </button>
          </div>
          <Check label="خط نام و نام خانوادگی" checked={box.name_line} disabled={disabled} onChange={(name_line) => setBox(b, { name_line })} />
          <Check label="خط تاریخ" checked={box.date_line} disabled={disabled} onChange={(date_line) => setBox(b, { date_line })} />
        </fieldset>
      ))}
      <button
        type="button"
        className={smallButton}
        disabled={disabled || element.boxes.length >= MAX_SIGNATURE_BOXES}
        onClick={() => set({ boxes: [...element.boxes, { caption: "امضا", name_line: true, date_line: true }] })}
      >
        + کادر امضا
      </button>
      <Check label="کادر «محل مهر»" checked={element.stamp} disabled={disabled} onChange={(stamp) => set({ stamp })} />
      <Field label="ارتفاع کادرها (میلی‌متر)">
        <NumberInput value={element.height} min={15} max={60} disabled={disabled} onChange={(height) => set({ height })} />
      </Field>
    </div>
  );
}
