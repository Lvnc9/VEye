"use client";

import { useEffect, useState } from "react";

/** A text box that reports its value 300 ms after typing stops, so a filter doesn't
 *  fire a request per keystroke. Give it a new `key` to reset it from outside. */
export function DebouncedInput({
  value,
  onCommit,
  placeholder,
  ariaLabel,
  className,
}: {
  value: string;
  onCommit: (value: string) => void;
  placeholder: string;
  ariaLabel: string;
  className?: string;
}) {
  const [text, setText] = useState(value);

  useEffect(() => {
    if (text === value) return;
    const timer = setTimeout(() => onCommit(text), 300);
    return () => clearTimeout(timer);
  }, [text, value, onCommit]);

  return (
    <input
      type="search"
      value={text}
      onChange={(event) => setText(event.target.value)}
      placeholder={placeholder}
      aria-label={ariaLabel}
      className={className ?? "w-full max-w-xs rounded border border-slate-300 bg-white px-3 py-2 text-sm"}
    />
  );
}
