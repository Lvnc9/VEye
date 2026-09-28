"use client";

import { useState } from "react";
import type { AttachmentSection } from "@/lib/types";
import { Code } from "../Code";
import { StatusBadge } from "../StatusBadge";
import { DocumentPicker } from "./DocumentPicker";
import { AddButton, IconButton, inputClass, type BlockProps } from "./ui";
import { buttonClass } from "@/components/ui/Button";
import { X } from "lucide-react";

/**
 * ضمائم — captioned links to other controlled documents.
 *
 * Unlike V_1.0, a linked row can be removed (its "-" button only ever popped
 * *unlinked* rows, utils.py:2715-2720), a row with no document is reported rather
 * than silently dropped on save (only `all_labels` was serialized), and the row
 * shows the target's live status — an obsolete attachment is visibly obsolete.
 */
export function AttachmentBlock({
  section,
  disabled,
  update,
  documentId,
}: BlockProps<AttachmentSection> & { documentId: number }) {
  const [picking, setPicking] = useState<number | null>(null);

  return (
    <div className="space-y-3">
      {section.items.map((item, position) => (
        <div key={position} className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-slate-50/40 p-3">
          <input
            type="text"
            value={item.caption}
            disabled={disabled}
            maxLength={255}
            placeholder="عنوان ضمیمه را بنویسید"
            onChange={(event) =>
              update((s) => ({
                ...s,
                items: s.items.map((it, i) => (i === position ? { ...it, caption: event.target.value } : it)),
              }))
            }
            className={`${inputClass} min-w-56 flex-1`}
          />

          {item.document ? (
            <span className="flex items-center gap-2 text-sm">
              <Code>{item.document.full_code}</Code>
              <span className="max-w-48 truncate text-slate-600" title={item.document.title}>
                {item.document.title}
              </span>
              <StatusBadge status={item.document.status} label={item.document.status_label} />
            </span>
          ) : (
            <span className="text-sm text-rose-600">مستندی انتخاب نشده</span>
          )}

          {!disabled && (
            <button
              type="button"
              onClick={() => setPicking(position)}
              className={buttonClass({ size: "sm" })}
            >
              {item.document ? "تغییر مستند" : "انتخاب مستند"}
            </button>
          )}
          {!disabled && (
            <IconButton
              label="حذف این ضمیمه"
              tone="danger"
              onClick={() => update((s) => ({ ...s, items: s.items.filter((_, i) => i !== position) }))}
            >
              <X />
            </IconButton>
          )}
        </div>
      ))}

      {section.items.length === 0 && <p className="text-sm text-slate-400">ضمیمه‌ای ثبت نشده است.</p>}

      {!disabled && (
        <AddButton onClick={() => update((s) => ({ ...s, items: [...s.items, { caption: "", document: null }] }))}>
          افزودن ضمیمه
        </AddButton>
      )}

      {picking !== null && (
        <DocumentPicker
          excludeId={documentId}
          onClose={() => setPicking(null)}
          onSelect={(target) => {
            const position = picking;
            setPicking(null);
            update((s) => ({
              ...s,
              items: s.items.map((it, i) => (i === position ? { ...it, document: target } : it)),
            }));
          }}
        />
      )}
    </div>
  );
}
