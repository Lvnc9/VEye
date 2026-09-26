"use client";

import { FieldLabel, inputClass } from "./ui";

/** «پاورقی»: the two free texts printed at the foot of every page. */
export function FootnoteFields({
  footnote1,
  footnote2,
  disabled,
  onChange,
}: {
  footnote1: string;
  footnote2: string;
  disabled: boolean;
  onChange: (next: { footnote1: string; footnote2: string }) => void;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <label className="block">
        <FieldLabel>متن آزاد</FieldLabel>
        <input
          type="text"
          value={footnote1}
          disabled={disabled}
          maxLength={255}
          placeholder="مثال: واحد برنامه ریزی شرکت"
          onChange={(event) => onChange({ footnote1: event.target.value, footnote2 })}
          className={inputClass}
        />
      </label>
      <label className="block">
        <FieldLabel>متن دلخواه</FieldLabel>
        <input
          type="text"
          value={footnote2}
          disabled={disabled}
          maxLength={255}
          placeholder="محل تایپ متن دلخواه"
          onChange={(event) => onChange({ footnote1, footnote2: event.target.value })}
          className={inputClass}
        />
      </label>
    </div>
  );
}
