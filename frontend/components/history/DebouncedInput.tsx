"use client";

import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { controlClass } from "@/components/ui/Field";
import { cx } from "@/components/ui/cx";

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
    <div className={cx("relative", className ?? "w-full sm:w-72")}>
      <Search className="pointer-events-none absolute inset-y-0 right-3 my-auto size-4 text-slate-400" />
      <input
        type="search"
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder={placeholder}
        aria-label={ariaLabel}
        className={cx(controlClass, "h-10 w-full pr-9")}
      />
    </div>
  );
}
