"use client";

import { useRef, useState, type KeyboardEvent } from "react";
import { applyStyle, parseMarkers, type Style } from "@/lib/rich-text";

const BUTTONS: { style: Style; label: string; title: string; className: string }[] = [
  { style: "bold", label: "B", title: "پررنگ (Ctrl+B)", className: "font-bold" },
  { style: "italic", label: "I", title: "مایل (Ctrl+I)", className: "italic" },
  { style: "underline", label: "U", title: "زیرخط (Ctrl+U)", className: "underline" },
];

const KEY_STYLE: Record<string, Style> = { b: "bold", i: "italic", u: "underline" };

/**
 * A textarea with V_1.0's B / I / U buttons (poster's «Writing Stage»,
 * utils.py:1756+). The formatting is stored as inline markers in the text —
 * **bold**, ~~italic~~, --underline-- — exactly what V_1.0's editor wrote and its
 * PDF renderer reads, so there is no conversion step.
 */
export function RichTextArea({
  value,
  onChange,
  disabled,
  placeholder,
  rows = 6,
}: {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  placeholder?: string;
  rows?: number;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const [preview, setPreview] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  function apply(style: Style) {
    const element = ref.current;
    if (!element || disabled) return;

    if (element.selectionStart === element.selectionEnd) {
      setNotice("ابتدا بخشی از متن را انتخاب کنید.");
      return;
    }
    const result = applyStyle(value, element.selectionStart, element.selectionEnd, style);
    if (result.error) {
      // The PDF renderer can't nest one style inside another.
      setNotice("درون یک بخش قالب‌بندی‌شده نمی‌توان قالب دیگری اعمال کرد. کل آن بخش را انتخاب کنید.");
      return;
    }
    setNotice(null);
    if (result.text !== value) onChange(result.text);
    // Restore the selection once React has re-rendered the new value.
    requestAnimationFrame(() => {
      element.focus();
      element.setSelectionRange(result.selStart, result.selEnd);
    });
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (!(event.ctrlKey || event.metaKey)) return;
    const style = KEY_STYLE[event.key.toLowerCase()];
    if (style) {
      event.preventDefault();
      apply(style);
    }
  }

  return (
    <div className="space-y-2">
      {!disabled && (
        <div className="flex items-center gap-1">
          {BUTTONS.map((button) => (
            <button
              key={button.style}
              type="button"
              onClick={() => apply(button.style)}
              title={button.title}
              aria-label={button.title}
              className={`h-8 w-8 rounded border border-slate-300 bg-white text-sm text-slate-700 hover:bg-slate-100 ${button.className}`}
            >
              {button.label}
            </button>
          ))}
          <button
            type="button"
            onClick={() => setPreview((open) => !open)}
            className="ms-2 rounded px-2 py-1 text-xs text-slate-500 hover:bg-slate-100"
          >
            {preview ? "پنهان کردن پیش‌نمایش" : "پیش‌نمایش"}
          </button>
        </div>
      )}

      <textarea
        ref={ref}
        value={value}
        rows={rows}
        disabled={disabled}
        placeholder={placeholder}
        dir="auto"
        onChange={(event) => {
          setNotice(null);
          onChange(event.target.value);
        }}
        onKeyDown={handleKeyDown}
        className="w-full resize-y rounded border border-slate-300 bg-white px-3 py-2 text-sm leading-7 focus:border-slate-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-600"
      />

      {notice && <p className="text-xs text-amber-700">{notice}</p>}

      {preview && (
        <div
          dir="auto"
          className="whitespace-pre-wrap rounded border border-dashed border-slate-300 bg-slate-50 px-3 py-2 text-sm leading-7"
        >
          {value.split("\n").map((line, lineIndex) => (
            <div key={lineIndex} className="min-h-7">
              {parseMarkers(line).map((run, runIndex) =>
                run.style === "bold" ? (
                  <strong key={runIndex}>{run.text}</strong>
                ) : run.style === "italic" ? (
                  <em key={runIndex}>{run.text}</em>
                ) : run.style === "underline" ? (
                  <u key={runIndex}>{run.text}</u>
                ) : (
                  <span key={runIndex}>{run.text}</span>
                ),
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
