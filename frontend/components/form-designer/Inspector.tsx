"use client";

import type { ReactNode } from "react";
import { MAX_LABEL, MAX_TEXT, elementLabel, type FormElement, type FormSettings } from "@/lib/form-designer";
import { RichTextArea } from "@/components/designer/RichTextArea";
import { FieldLabel, inputClass } from "@/components/designer/ui";

export type ElementUpdate = (updater: (element: FormElement) => FormElement) => void;

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <FieldLabel>{label}</FieldLabel>
      {children}
    </label>
  );
}

function Select<T extends string | number>({
  value,
  options,
  disabled,
  onChange,
}: {
  value: T;
  options: [T, string][];
  disabled: boolean;
  onChange: (value: T) => void;
}) {
  return (
    <select
      value={String(value)}
      disabled={disabled}
      onChange={(event) => {
        const picked = options.find(([option]) => String(option) === event.target.value);
        if (picked) onChange(picked[0]);
      }}
      className={inputClass}
    >
      {options.map(([option, label]) => (
        <option key={String(option)} value={String(option)}>
          {label}
        </option>
      ))}
    </select>
  );
}

function NumberInput({
  value,
  min,
  max,
  step = 1,
  disabled,
  onChange,
}: {
  value: number;
  min: number;
  max: number;
  step?: number;
  disabled: boolean;
  onChange: (value: number) => void;
}) {
  return (
    <input
      type="number"
      dir="ltr"
      value={value}
      min={min}
      max={max}
      step={step}
      disabled={disabled}
      onChange={(event) => {
        const next = Number(event.target.value);
        // Out-of-range typing is clamped rather than sent for the server to refuse.
        if (event.target.value !== "" && Number.isFinite(next)) onChange(Math.min(max, Math.max(min, next)));
      }}
      className={`${inputClass} text-left`}
    />
  );
}

export function Check({
  label,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  checked: boolean;
  disabled: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-slate-700">
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} />
      {label}
    </label>
  );
}

const ALIGN_OPTIONS: ["right" | "center" | "left", string][] = [
  ["right", "راست"],
  ["center", "وسط"],
  ["left", "چپ"],
];

/** The properties of the selected element. */
export function ElementInspector({
  element,
  disabled,
  update,
}: {
  element: FormElement;
  disabled: boolean;
  update: ElementUpdate;
}) {
  // Each setter keeps the element's kind: `update` receives the latest element.
  const set = <E extends FormElement>(patch: Partial<E>) => update((current) => ({ ...current, ...patch }) as FormElement);

  return (
    <div className="space-y-4">
      <p className="text-sm font-semibold text-slate-800">{elementLabel(element.kind)}</p>

      {element.kind === "heading" && (
        <>
          <Field label="متن عنوان">
            <input
              value={element.text}
              maxLength={MAX_LABEL}
              disabled={disabled}
              onChange={(event) => set({ text: event.target.value })}
              className={inputClass}
            />
          </Field>
          <Field label="شکل">
            <Select
              value={element.style}
              disabled={disabled}
              options={[
                ["band", "نوار رنگی"],
                ["underline", "با خط زیر"],
                ["plain", "ساده"],
              ]}
              onChange={(style) => set({ style })}
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="سطح">
              <Select
                value={element.level}
                disabled={disabled}
                options={[
                  [1, "۱ (اصلی)"],
                  [2, "۲"],
                  [3, "۳"],
                ]}
                onChange={(level) => set({ level })}
              />
            </Field>
            <Field label="چینش">
              <Select
                value={element.align}
                disabled={disabled}
                options={ALIGN_OPTIONS.slice(0, 2) as ["right" | "center", string][]}
                onChange={(align) => set({ align })}
              />
            </Field>
          </div>
          <Check label="شماره‌گذاری خودکار (۱، ۲، ۲.۱ …)" checked={element.numbered} disabled={disabled} onChange={(numbered) => set({ numbered })} />
        </>
      )}

      {element.kind === "text" && (
        <>
          <Field label="متن">
            <RichTextArea
              value={element.text}
              disabled={disabled}
              rows={6}
              placeholder="مثال: لطفاً فرم را با خودکار آبی و خوانا تکمیل کنید."
              onChange={(text) => set({ text: text.slice(0, MAX_TEXT) })}
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="چینش">
              <Select value={element.align} disabled={disabled} options={ALIGN_OPTIONS} onChange={(align) => set({ align })} />
            </Field>
            <Field label="اندازه قلم">
              <Select
                value={element.size}
                disabled={disabled}
                options={[[0, "پیش‌فرض فرم"], ...[8, 9, 10, 11, 12, 14, 16, 18].map((n) => [n, n.toLocaleString("fa-IR")] as [number, string])]}
                onChange={(size) => set({ size })}
              />
            </Field>
          </div>
          <Check label="داخل کادر" checked={element.boxed} disabled={disabled} onChange={(boxed) => set({ boxed })} />
        </>
      )}

      {element.kind === "divider" && (
        <>
          <Field label="نوع خط">
            <Select
              value={element.style}
              disabled={disabled}
              options={[
                ["solid", "ممتد"],
                ["dashed", "خط‌چین"],
                ["dotted", "نقطه‌چین"],
                ["double", "دوخطی"],
              ]}
              onChange={(style) => set({ style })}
            />
          </Field>
          <Field label="ضخامت (پوینت)">
            <NumberInput value={element.thickness} min={0.25} max={3} step={0.25} disabled={disabled} onChange={(thickness) => set({ thickness })} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="فاصله از بالا (میلی‌متر)">
              <NumberInput value={element.space_before} min={0} max={30} disabled={disabled} onChange={(space_before) => set({ space_before })} />
            </Field>
            <Field label="فاصله از پایین (میلی‌متر)">
              <NumberInput value={element.space_after} min={0} max={30} disabled={disabled} onChange={(space_after) => set({ space_after })} />
            </Field>
          </div>
        </>
      )}

      {element.kind === "spacer" && (
        <Field label="ارتفاع (میلی‌متر)">
          <NumberInput value={element.height} min={1} max={150} disabled={disabled} onChange={(height) => set({ height })} />
        </Field>
      )}

      {element.kind === "page_break" && (
        <p className="text-sm text-slate-600">جزء بعدی از بالای یک صفحهٔ تازه چاپ می‌شود.</p>
      )}
    </div>
  );
}

/** The whole form's settings: page, header options. */
export function PageSettingsPanel({
  settings,
  disabled,
  onChange,
}: {
  settings: FormSettings;
  disabled: boolean;
  onChange: (settings: FormSettings) => void;
}) {
  const header = (patch: Partial<FormSettings["header"]>) => onChange({ ...settings, header: { ...settings.header, ...patch } });
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <Field label="جهت صفحه">
          <Select
            value={settings.orientation}
            disabled={disabled}
            options={[
              ["portrait", "عمودی"],
              ["landscape", "افقی"],
            ]}
            onChange={(orientation) => onChange({ ...settings, orientation })}
          />
        </Field>
        <Field label="اندازه قلم">
          <Select
            value={settings.base_font_size}
            disabled={disabled}
            options={[8, 9, 10, 11, 12, 13, 14].map((n) => [n, n.toLocaleString("fa-IR")] as [number, string])}
            onChange={(base_font_size) => onChange({ ...settings, base_font_size })}
          />
        </Field>
      </div>
      <Field label="زیرعنوان سربرگ">
        <input
          value={settings.header.subtitle}
          maxLength={255}
          disabled={disabled}
          placeholder="مثال: واحد منابع انسانی"
          onChange={(event) => header({ subtitle: event.target.value })}
          className={inputClass}
        />
      </Field>
      <Check
        label="نام شرکت در سربرگ"
        checked={settings.header.show_company_name}
        disabled={disabled}
        onChange={(show_company_name) => header({ show_company_name })}
      />
      <Check
        label="شماره / تاریخ / پیوست در بالای صفحهٔ اول"
        checked={settings.header.show_letter_box}
        disabled={disabled}
        onChange={(show_letter_box) => header({ show_letter_box })}
      />
      <Check
        label="جدول امضای تدوین، تایید و تصویب در پایان فرم"
        checked={settings.approval_strip}
        disabled={disabled}
        onChange={(approval_strip) => onChange({ ...settings, approval_strip })}
      />
    </div>
  );
}
