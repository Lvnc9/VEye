"use client";

import { ArrowLeft, ArrowRight, ChevronDown, ChevronUp, X } from "lucide-react";
import {
  ANSWER_KIND_LABELS,
  MAX_MATRIX_ITEMS,
  MAX_OPTIONS,
  MAX_QUESTIONS,
  MAX_SCALE,
  type AnswerKind,
  type ChoicesProps,
  type MatrixProps,
  type QuestionsProps,
  COLUMN_TYPE_LABELS,
  FIELD_TYPE_LABELS,
  MAX_COLUMNS,
  MAX_HEADER_ROWS,
  MAX_TABLE_ROWS,
  MIN_COLUMN_WIDTH,
  addColumn,
  moveColumn,
  removeColumn,
  resizeRows,
  setColumnWidths,
  type Align,
  type ColumnType,
  type TableProps,
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
  "inline-flex h-7 min-w-7 items-center justify-center gap-1 rounded-md border border-slate-200 bg-white px-2 text-xs text-slate-700 shadow-xs " +
  "transition-[background-color,transform] duration-150 hover:bg-slate-50 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40 " +
  "disabled:active:scale-100 [&_svg]:size-3.5";

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
          <fieldset key={r} className="space-y-2 rounded-xl border border-slate-200 bg-slate-50/40 p-2.5">
            <legend className="flex w-full items-center gap-1 px-1 text-xs font-bold text-slate-600">
              <span className="flex-1">ردیف {(r + 1).toLocaleString("fa-IR")}</span>
              <button type="button" className={smallButton} disabled={disabled || r === 0} aria-label="ردیف بالا" onClick={() => set({ rows: moveElement(element.rows, r, r - 1) })}>
                <ChevronUp />
              </button>
              <button
                type="button"
                className={smallButton}
                disabled={disabled || r === element.rows.length - 1}
                aria-label="ردیف پایین"
                onClick={() => set({ rows: moveElement(element.rows, r, r + 1) })}
              >
                <ChevronDown />
              </button>
              <button
                type="button"
                className={`${smallButton} text-rose-600 hover:bg-rose-50`}
                disabled={disabled || element.rows.length === 1}
                aria-label="حذف ردیف"
                onClick={() => set({ rows: element.rows.filter((_, i) => i !== r) })}
              >
                <X />
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
                    className={`${smallButton} text-rose-600 hover:bg-rose-50`}
                    disabled={disabled || row.cells.length === 1}
                    aria-label="حذف خانه"
                    onClick={() => {
                      const cells = row.cells.filter((_, i) => i !== c);
                      setRow(r, withWidths(cells, evenWidths(cells.length)));
                    }}
                  >
                    <X />
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
        <fieldset key={b} className="space-y-2 rounded-xl border border-slate-200 bg-slate-50/40 p-2.5">
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
              className={`${smallButton} text-rose-600 hover:bg-rose-50`}
              disabled={disabled || element.boxes.length === 1}
              aria-label="حذف کادر"
              onClick={() => set({ boxes: element.boxes.filter((_, i) => i !== b) })}
            >
              <X />
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

export function TableEditor({ element, disabled, set }: { element: TableProps; disabled: boolean; set: Patch<TableProps> }) {
  const table = (updater: (t: TableProps) => TableProps) => set(updater(element));
  const widths = element.columns.map((c) => c.width);
  const count = element.columns.length;
  const bodyRoom = MAX_TABLE_ROWS - element.rows.length;

  return (
    <div className="space-y-4">
      <Field label="عنوان جدول (اختیاری)">
        <input
          value={element.title}
          maxLength={MAX_LABEL}
          disabled={disabled}
          placeholder="مثال: سوابق تحصیلی"
          onChange={(event) => set({ title: event.target.value })}
          className={inputClass}
        />
      </Field>

      <div className="space-y-2">
        <p className="text-sm font-bold text-slate-700">ستون‌ها (از راست به چپ)</p>
        {element.columns.map((column, c) => (
          <div key={c} className="space-y-1 rounded-xl border border-slate-200 bg-slate-50/40 p-2.5">
            <div className="flex items-center gap-1 text-xs text-slate-600">
              <span className="flex-1 truncate">
                ستون {(c + 1).toLocaleString("fa-IR")}
                {element.header[element.header.length - 1][c] ? ` — ${element.header[element.header.length - 1][c]}` : ""}
              </span>
              <button type="button" className={smallButton} disabled={disabled || c === 0} aria-label="جابه‌جایی به راست" onClick={() => table((t) => moveColumn(t, c, c - 1))}>
                <ArrowRight />
              </button>
              <button type="button" className={smallButton} disabled={disabled || c === count - 1} aria-label="جابه‌جایی به چپ" onClick={() => table((t) => moveColumn(t, c, c + 1))}>
                <ArrowLeft />
              </button>
              <button
                type="button"
                className={`${smallButton} text-rose-600 hover:bg-rose-50`}
                disabled={disabled || count === 1}
                aria-label="حذف ستون"
                onClick={() => table((t) => removeColumn(t, c))}
              >
                <X />
              </button>
            </div>
            <div className="grid grid-cols-[1fr_4.5rem_4.5rem] gap-1">
              <Select<ColumnType>
                value={column.type}
                disabled={disabled}
                options={Object.entries(COLUMN_TYPE_LABELS) as [ColumnType, string][]}
                onChange={(type) => table((t) => ({ ...t, columns: t.columns.map((x, i) => (i === c ? { ...x, type } : x)) }))}
              />
              <Select<Align>
                value={column.align}
                disabled={disabled}
                options={[
                  ["right", "راست"],
                  ["center", "وسط"],
                  ["left", "چپ"],
                ]}
                onChange={(align) => table((t) => ({ ...t, columns: t.columns.map((x, i) => (i === c ? { ...x, align } : x)) }))}
              />
              <NumberInput
                value={column.width}
                min={MIN_COLUMN_WIDTH}
                max={100}
                disabled={disabled || count === 1}
                onChange={(width) => table((t) => setColumnWidths(t, setWidth(widths, c, width, MIN_COLUMN_WIDTH)))}
              />
            </div>
          </div>
        ))}
        <div className="flex flex-wrap gap-1">
          <button type="button" className={smallButton} disabled={disabled || count >= MAX_COLUMNS} onClick={() => table(addColumn)}>
            + ستون
          </button>
          <button type="button" className={smallButton} disabled={disabled} onClick={() => table((t) => setColumnWidths(t, evenWidths(count)))}>
            پهنای برابر
          </button>
        </div>
        <p className="text-xs text-slate-500">
          پهنا درصدی از جدول است. روی خود جدول هم می‌توانید مرز ستون‌ها را بکشید. متن سرستون‌ها و ردیف‌های متن‌دار را روی جدول بنویسید؛ برای ادغام، خانه‌ای را انتخاب کنید (با Shift چند خانه) و از نوار بالای جدول استفاده کنید.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Field label="ردیف‌های سرستون">
          <NumberInput
            value={element.header.length}
            min={1}
            max={MAX_HEADER_ROWS}
            disabled={disabled}
            onChange={(n) => table((t) => resizeRows(t, "header", n))}
          />
        </Field>
        <Field label="ردیف‌های متن‌دار">
          <NumberInput
            value={element.rows.length}
            min={0}
            max={MAX_TABLE_ROWS - element.blank_rows}
            disabled={disabled}
            onChange={(n) => table((t) => resizeRows(t, "rows", n))}
          />
        </Field>
        <Field label="ردیف‌های خالی">
          <NumberInput value={element.blank_rows} min={0} max={bodyRoom} disabled={disabled} onChange={(blank_rows) => set({ blank_rows })} />
        </Field>
        <Field label="ارتفاع ردیف (میلی‌متر)">
          <NumberInput value={element.row_height} min={5} max={30} disabled={disabled} onChange={(row_height) => set({ row_height })} />
        </Field>
        <Field label="خطوط جدول">
          <Select
            value={element.borders}
            disabled={disabled}
            options={[
              ["all", "همهٔ خطوط"],
              ["outer", "فقط قاب"],
              ["horizontal", "فقط افقی"],
              ["none", "بدون خط"],
            ]}
            onChange={(borders) => set({ borders })}
          />
        </Field>
        <Field label="اندازه قلم">
          <Select
            value={element.font_size}
            disabled={disabled}
            options={[[0, "پیش‌فرض"], ...[7, 8, 9, 10, 11, 12, 14].map((n) => [n, n.toLocaleString("fa-IR")] as [number, string])]}
            onChange={(font_size) => set({ font_size })}
          />
        </Field>
      </div>
      <Check label="سرستون با زمینهٔ رنگی" checked={element.header_shade} disabled={disabled} onChange={(header_shade) => set({ header_shade })} />
      <Check label="تکرار سرستون در هر صفحه" checked={element.repeat_header} disabled={disabled} onChange={(repeat_header) => set({ repeat_header })} />
    </div>
  );
}

/** An editable list of short texts: options, items, grades. */
function StringList({
  values,
  min,
  max,
  disabled,
  addLabel,
  onChange,
}: {
  values: string[];
  min: number;
  max: number;
  disabled: boolean;
  addLabel: string;
  onChange: (values: string[]) => void;
}) {
  return (
    <div className="space-y-1">
      {values.map((value, i) => (
        <div key={i} className="flex gap-1">
          <input
            value={value}
            maxLength={MAX_LABEL}
            disabled={disabled}
            aria-label={`مورد ${(i + 1).toLocaleString("fa-IR")}`}
            onChange={(event) => onChange(values.map((v, j) => (j === i ? event.target.value : v)))}
            className={`${inputClass} py-1`}
          />
          <button type="button" className={smallButton} disabled={disabled || i === 0} aria-label="بالا" onClick={() => onChange(moveElement(values, i, i - 1))}>
            <ChevronUp />
          </button>
          <button
            type="button"
            className={`${smallButton} text-rose-600 hover:bg-rose-50`}
            disabled={disabled || values.length <= min}
            aria-label="حذف"
            onClick={() => onChange(values.filter((_, j) => j !== i))}
          >
            <X />
          </button>
        </div>
      ))}
      <button type="button" className={smallButton} disabled={disabled || values.length >= max} onClick={() => onChange([...values, ""])}>
        + {addLabel}
      </button>
    </div>
  );
}

export function ChoicesEditor({ element, disabled, set }: { element: ChoicesProps; disabled: boolean; set: Patch<ChoicesProps> }) {
  return (
    <div className="space-y-4">
      <Field label="پرسش">
        <input value={element.label} maxLength={MAX_LABEL} disabled={disabled} onChange={(event) => set({ label: event.target.value })} className={inputClass} />
      </Field>
      <div>
        <p className="mb-1 text-sm font-bold text-slate-700">گزینه‌ها</p>
        <StringList values={element.options} min={1} max={MAX_OPTIONS} disabled={disabled} addLabel="گزینه" onChange={(options) => set({ options })} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="چیدمان">
          <Select
            value={element.layout}
            disabled={disabled}
            options={[
              ["inline", "پشت سر هم"],
              ["vertical", "زیر هم"],
              ["columns", "چند ستونی"],
            ]}
            onChange={(layout) => set({ layout })}
          />
        </Field>
        <Field label="شکل">
          <Select
            value={element.shape}
            disabled={disabled}
            options={[
              ["square", "مربع (چندگزینه‌ای)"],
              ["circle", "دایره (تک‌گزینه‌ای)"],
            ]}
            onChange={(shape) => set({ shape })}
          />
        </Field>
      </div>
      {element.layout === "columns" && (
        <Field label="تعداد ستون">
          <NumberInput value={element.columns} min={2} max={4} disabled={disabled} onChange={(columns) => set({ columns })} />
        </Field>
      )}
      <Check label="گزینهٔ «سایر: ……»" checked={element.other} disabled={disabled} onChange={(other) => set({ other })} />
    </div>
  );
}

export function MatrixEditor({ element, disabled, set }: { element: MatrixProps; disabled: boolean; set: Patch<MatrixProps> }) {
  return (
    <div className="space-y-4">
      <Field label="عنوان (اختیاری)">
        <input value={element.title} maxLength={MAX_LABEL} disabled={disabled} placeholder="مثال: ارزیابی عملکرد" onChange={(event) => set({ title: event.target.value })} className={inputClass} />
      </Field>
      <div>
        <p className="mb-1 text-sm font-bold text-slate-700">موارد (ردیف‌ها)</p>
        <StringList values={element.items} min={1} max={MAX_MATRIX_ITEMS} disabled={disabled} addLabel="مورد" onChange={(items) => set({ items })} />
      </div>
      <div>
        <p className="mb-1 text-sm font-bold text-slate-700">درجه‌ها (ستون‌ها)</p>
        <StringList values={element.scale} min={2} max={MAX_SCALE} disabled={disabled} addLabel="درجه" onChange={(scale) => set({ scale })} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="عنوان ستون موارد">
          <input value={element.item_title} maxLength={MAX_LABEL} disabled={disabled} onChange={(event) => set({ item_title: event.target.value })} className={inputClass} />
        </Field>
        <Field label="پهنای ستون موارد (درصد)">
          <NumberInput value={element.item_width} min={20} max={70} disabled={disabled} onChange={(item_width) => set({ item_width })} />
        </Field>
        <Field label="شکل">
          <Select
            value={element.shape}
            disabled={disabled}
            options={[
              ["circle", "دایره"],
              ["square", "مربع"],
            ]}
            onChange={(shape) => set({ shape })}
          />
        </Field>
      </div>
      <Check label="شماره‌گذاری موارد" checked={element.numbered} disabled={disabled} onChange={(numbered) => set({ numbered })} />
      <Check label="ستون توضیحات" checked={element.comment} disabled={disabled} onChange={(comment) => set({ comment })} />
      {element.comment && (
        <Field label="عنوان ستون توضیحات">
          <input value={element.comment_title} maxLength={MAX_LABEL} disabled={disabled} onChange={(event) => set({ comment_title: event.target.value })} className={inputClass} />
        </Field>
      )}
    </div>
  );
}

export function QuestionsEditor({ element, disabled, set }: { element: QuestionsProps; disabled: boolean; set: Patch<QuestionsProps> }) {
  const setItem = (i: number, patch: Partial<QuestionsProps["items"][number]>) =>
    set({ items: element.items.map((item, j) => (j === i ? { ...item, ...patch } : item)) });
  return (
    <div className="space-y-3">
      <Check label="شماره‌گذاری پرسش‌ها" checked={element.numbered} disabled={disabled} onChange={(numbered) => set({ numbered })} />
      {element.items.map((item, i) => (
        <fieldset key={i} className="space-y-2 rounded-xl border border-slate-200 bg-slate-50/40 p-2.5">
          <legend className="flex w-full items-center gap-1 px-1 text-xs font-bold text-slate-600">
            <span className="flex-1">پرسش {(i + 1).toLocaleString("fa-IR")}</span>
            <button type="button" className={smallButton} disabled={disabled || i === 0} aria-label="بالا" onClick={() => set({ items: moveElement(element.items, i, i - 1) })}>
              <ChevronUp />
            </button>
            <button
              type="button"
              className={smallButton}
              disabled={disabled || i === element.items.length - 1}
              aria-label="پایین"
              onClick={() => set({ items: moveElement(element.items, i, i + 1) })}
            >
              <ChevronDown />
            </button>
            <button
              type="button"
              className={`${smallButton} text-rose-600 hover:bg-rose-50`}
              disabled={disabled || element.items.length === 1}
              aria-label="حذف پرسش"
              onClick={() => set({ items: element.items.filter((_, j) => j !== i) })}
            >
              <X />
            </button>
          </legend>
          <textarea
            value={item.text}
            maxLength={2000}
            rows={2}
            disabled={disabled}
            aria-label="متن پرسش"
            onChange={(event) => setItem(i, { text: event.target.value })}
            className={inputClass}
          />
          <div className="grid grid-cols-[1fr_5rem] gap-1">
            <Select<AnswerKind>
              value={item.answer}
              disabled={disabled}
              options={Object.entries(ANSWER_KIND_LABELS) as [AnswerKind, string][]}
              onChange={(answer) => setItem(i, { answer })}
            />
            {item.answer === "lines" && (
              <NumberInput value={item.lines} min={1} max={15} disabled={disabled} onChange={(lines) => setItem(i, { lines })} />
            )}
            {item.answer === "box" && (
              <NumberInput value={item.height} min={10} max={150} disabled={disabled} onChange={(height) => setItem(i, { height })} />
            )}
          </div>
        </fieldset>
      ))}
      <button
        type="button"
        className={smallButton}
        disabled={disabled || element.items.length >= MAX_QUESTIONS}
        onClick={() => set({ items: [...element.items, { text: "", answer: "lines", lines: 2, height: 25 }] })}
      >
        + پرسش
      </button>
      <p className="text-xs text-slate-500">عدد کنار نوع پاسخ: تعداد خط، یا ارتفاع کادر به میلی‌متر.</p>
    </div>
  );
}
