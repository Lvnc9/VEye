"use client";

import type { ShortSection } from "@/lib/types";
import { AddButton, IconButton, inputClass, type BlockProps } from "./ui";

/** تشریحی کوتاه — a list of one-line entries (utils.py:2722-2881). V_1.0 started
 *  it with two and could add more or remove the last. */
export function ShortBlock({ section, index, disabled, update }: BlockProps<ShortSection>) {
  const setLine = (position: number, value: string) =>
    update((s) => ({ ...s, lines: s.lines.map((line, i) => (i === position ? value : line)) }));

  return (
    <div className="space-y-2">
      {section.lines.map((line, position) => (
        <div key={position} className="flex items-center gap-2">
          <input
            type="text"
            value={line}
            disabled={disabled}
            maxLength={2000}
            // V_1.0's numbering hint: "1-", then "1-2", "1-3"...
            placeholder={position === 0 ? `${index}-` : `${index}-${position + 1}`}
            onChange={(event) => setLine(position, event.target.value)}
            className={inputClass}
          />
          {!disabled && (
            <IconButton
              label="حذف این خط"
              tone="danger"
              onClick={() => update((s) => ({ ...s, lines: s.lines.filter((_, i) => i !== position) }))}
            >
              ✕
            </IconButton>
          )}
        </div>
      ))}
      {!disabled && <AddButton onClick={() => update((s) => ({ ...s, lines: [...s.lines, ""] }))}>افزودن خط</AddButton>}
    </div>
  );
}
