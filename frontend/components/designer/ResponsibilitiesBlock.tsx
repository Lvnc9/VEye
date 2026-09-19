"use client";

import { RESPONSIBILITY_ROLE_LABELS, TITLE_MATRIX, type ResponsibilitiesSection, type RoleRow } from "@/lib/types";
import { AddButton, FieldLabel, IconButton, inputClass, type BlockProps } from "./ui";

/** The nine job titles from the personnel matrix, offered as suggestions. The
 *  fields stay free text: V_1.0's dropdowns for these each held a single
 *  hardcoded placeholder ('Organiztion Post' / 'SuperVisor', utils.py:1452,1476),
 *  so no real list of posts ever existed. */
const TITLE_SUGGESTIONS = Array.from(new Set(Object.values(TITLE_MATRIX)));

/** مسئولیت ها — four fixed rows (سمت / ناظر / توضیحات each) plus any number of
 *  description-only notes (utils.py:1325-1602). */
export function ResponsibilitiesBlock({ section, disabled, update }: BlockProps<ResponsibilitiesSection>) {
  const listId = `posts-${section.key}`;
  const setRole = (position: number, patch: Partial<RoleRow>) =>
    update((s) => ({ ...s, roles: s.roles.map((row, i) => (i === position ? { ...row, ...patch } : row)) }));

  return (
    <div className="space-y-5">
      <datalist id={listId}>
        {TITLE_SUGGESTIONS.map((title) => (
          <option key={title} value={title} />
        ))}
      </datalist>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-right text-sm">
          <thead className="text-slate-500">
            <tr>
              <th className="w-28 px-2 pb-2 font-medium">نقش</th>
              <th className="px-2 pb-2 font-medium">سمت</th>
              <th className="px-2 pb-2 font-medium">ناظر</th>
              <th className="px-2 pb-2 font-medium">توضیحات</th>
            </tr>
          </thead>
          <tbody>
            {section.roles.map((row, position) => (
              <tr key={row.role}>
                <td className="px-2 py-1 font-medium text-slate-800">{RESPONSIBILITY_ROLE_LABELS[row.role]}</td>
                <td className="px-2 py-1">
                  <input
                    type="text"
                    list={listId}
                    value={row.post}
                    disabled={disabled}
                    maxLength={255}
                    aria-label={`سمت ${RESPONSIBILITY_ROLE_LABELS[row.role]}`}
                    onChange={(event) => setRole(position, { post: event.target.value })}
                    className={inputClass}
                  />
                </td>
                <td className="px-2 py-1">
                  <input
                    type="text"
                    list={listId}
                    value={row.supervisor}
                    disabled={disabled}
                    maxLength={255}
                    aria-label={`ناظر ${RESPONSIBILITY_ROLE_LABELS[row.role]}`}
                    onChange={(event) => setRole(position, { supervisor: event.target.value })}
                    className={inputClass}
                  />
                </td>
                <td className="px-2 py-1">
                  <input
                    type="text"
                    value={row.text}
                    disabled={disabled}
                    maxLength={5000}
                    aria-label={`توضیحات ${RESPONSIBILITY_ROLE_LABELS[row.role]}`}
                    onChange={(event) => setRole(position, { text: event.target.value })}
                    className={inputClass}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="space-y-2">
        {section.notes.length > 0 && <FieldLabel>توضیحات بیشتر</FieldLabel>}
        {section.notes.map((note, position) => (
          <div key={position} className="flex items-center gap-2">
            <input
              type="text"
              value={note}
              disabled={disabled}
              maxLength={5000}
              onChange={(event) =>
                update((s) => ({ ...s, notes: s.notes.map((n, i) => (i === position ? event.target.value : n)) }))
              }
              className={inputClass}
            />
            {!disabled && (
              <IconButton
                label="حذف این توضیح"
                tone="danger"
                onClick={() => update((s) => ({ ...s, notes: s.notes.filter((_, i) => i !== position) }))}
              >
                ✕
              </IconButton>
            )}
          </div>
        ))}
        {!disabled && <AddButton onClick={() => update((s) => ({ ...s, notes: [...s.notes, ""] }))}>افزودن توضیح</AddButton>}
      </div>
    </div>
  );
}
