"use client";

import { formatJalali, todayJalali } from "@/lib/jalali";
import type { ChangesSection, PreviousChange } from "@/lib/types";
import { Code } from "../Code";
import { AddButton, IconButton, inputClass, type BlockProps } from "./ui";

/**
 * جدول تغییرات — the change log.
 *
 * Rows written in earlier revisions appear first as frozen history, derived from
 * the revision chain rather than copied (so nothing is duplicated and nothing can
 * be edited after the fact). This edition's rows follow, and are the only ones
 * that can change. The edition number is the document's revision, and the date is
 * assigned by the server when a row is first saved.
 *
 * V_1.0 pre-filled every new table with two hardcoded demo rows (utils.py:1243-1247)
 * and only ever reached back one revision (deliver_convert.py:163-197).
 */
export function ChangesBlock({
  section,
  index,
  disabled,
  update,
  previous,
  revisionDisplay,
}: BlockProps<ChangesSection> & { previous: PreviousChange[]; revisionDisplay: string }) {
  const offset = previous.length;
  const today = todayJalali();

  return (
    <div className="space-y-3">
      {previous.length > 0 && (
        <p className="text-xs text-slate-500">
          ردیف‌های ویرایش‌های قبلی به‌صورت خودکار نمایش داده می‌شوند و قابل تغییر نیستند.
        </p>
      )}

      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-right text-sm">
          <thead className="text-slate-500">
            <tr>
              <th className="w-16 px-2 pb-2 font-medium">ردیف</th>
              <th className="w-28 px-2 pb-2 font-medium">شماره ویرایش</th>
              <th className="w-32 px-2 pb-2 font-medium">تاریخ ویرایش</th>
              <th className="px-2 pb-2 font-medium">عنوان تغییرات *</th>
              <th className="w-10" />
            </tr>
          </thead>
          <tbody>
            {previous.map((row, position) => (
              <tr key={`prev-${row.id}`} className="bg-slate-50 text-slate-600">
                <td className="px-2 py-2">{position + 1}</td>
                <td className="px-2 py-2">
                  <Code>{row.revision_display}</Code>
                </td>
                <td className="px-2 py-2">{formatJalali(row.date)}</td>
                <td className="px-2 py-2">{row.text}</td>
                <td />
              </tr>
            ))}
            {section.rows.map((row, position) => (
              <tr key={row.id ?? `new-${position}`}>
                <td className="px-2 py-1">{offset + position + 1}</td>
                <td className="px-2 py-1">
                  <Code>{revisionDisplay}</Code>
                </td>
                <td className="px-2 py-1 text-slate-600">
                  {row.date ? formatJalali(row.date) : <span title="پس از ذخیره‌سازی ثبت می‌شود">{today}</span>}
                </td>
                <td className="px-2 py-1">
                  <input
                    type="text"
                    value={row.text}
                    disabled={disabled}
                    maxLength={5000}
                    placeholder={`${index}-${offset + position + 1}`}
                    onChange={(event) =>
                      update((s) => ({
                        ...s,
                        rows: s.rows.map((r, i) => (i === position ? { ...r, text: event.target.value } : r)),
                      }))
                    }
                    className={inputClass}
                  />
                </td>
                <td className="px-1 py-1">
                  {!disabled && (
                    <IconButton
                      label="حذف این ردیف"
                      tone="danger"
                      onClick={() => update((s) => ({ ...s, rows: s.rows.filter((_, i) => i !== position) }))}
                    >
                      ✕
                    </IconButton>
                  )}
                </td>
              </tr>
            ))}
            {previous.length === 0 && section.rows.length === 0 && (
              <tr>
                <td colSpan={5} className="px-2 py-4 text-center text-slate-400">
                  هنوز تغییری ثبت نشده است.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {!disabled && <AddButton onClick={() => update((s) => ({ ...s, rows: [...s.rows, { text: "" }] }))}>افزودن ردیف</AddButton>}
    </div>
  );
}
