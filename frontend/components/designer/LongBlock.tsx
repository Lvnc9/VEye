"use client";

import { useRef, useState, type ChangeEvent } from "react";
import { ApiError, apiUploadWithProgress } from "@/lib/api-client";
import { FileRow } from "@/components/FileRow";
import type { DocumentFileInfo, LongSection } from "@/lib/types";
import { RichTextArea } from "./RichTextArea";
import { AddButton, FieldLabel, IconButton, inputClass, type BlockProps } from "./ui";
import { buttonClass } from "@/components/ui/Button";
import { X } from "lucide-react";

/** The three upload buttons and the file types V_1.0's dialogs offered
 *  (utils.py:1638-1666; `xlsx` added — V_1.0 listed every Excel flavour except
 *  the common one). The server re-checks the extension; this only filters the picker. */
const ACCEPT = {
  picture: ".png,.jpg,.jpeg,.gif,.webp",
  document: ".docx,.pptx,.xlsx,.xlsm,.xlsb,.xls,.xltx,.pdf,.txt,.csv",
  video: ".mp4,.mov,.webm",
} as const;

type UploadKind = keyof typeof ACCEPT;

const UPLOAD_BUTTONS: { kind: UploadKind; label: string }[] = [
  { kind: "picture", label: "افزودن تصویر" },
  { kind: "document", label: "افزودن فایل" },
  { kind: "video", label: "افزودن ویدیو" },
];

interface PendingUpload {
  id: number;
  name: string;
  progress: number;
  controller: AbortController;
}

/**
 * تشریحی بلند — a heading, a rich-text body, any number of extra text boxes, and
 * uploaded files (utils.py:1604-2476).
 *
 * V_1.0 sent uploads to one shared bucket keyed by bare filename, so two
 * documents attaching different files with the same name shared one of them.
 * Here a file belongs to this document, and identical bytes are stored once.
 * Uploads are saved immediately; removing a file only detaches it, and it is
 * deleted when the document is saved.
 */
export function LongBlock({
  section,
  index,
  disabled,
  update,
  documentId,
  trackUpload,
}: BlockProps<LongSection> & {
  documentId: number;
  /** Called when an upload starts; returns the function to call when it ends.
   *  The page uses it to hold Save back — a save that ran mid-upload would sweep
   *  the just-uploaded (not yet attached) file away as an orphan. */
  trackUpload?: () => () => void;
}) {
  const [uploads, setUploads] = useState<PendingUpload[]>([]);
  const [error, setError] = useState<string | null>(null);
  const counter = useRef(0);
  const pickers = {
    picture: useRef<HTMLInputElement>(null),
    document: useRef<HTMLInputElement>(null),
    video: useRef<HTMLInputElement>(null),
  };

  async function upload(file: File) {
    counter.current += 1;
    const id = counter.current;
    const controller = new AbortController();
    const release = trackUpload?.();
    setUploads((current) => [...current, { id, name: file.name, progress: 0, controller }]);

    try {
      const form = new FormData();
      form.append("file", file);
      const info = await apiUploadWithProgress<DocumentFileInfo>(`/documents/${documentId}/files/`, form, {
        signal: controller.signal,
        onProgress: (fraction) =>
          setUploads((current) => current.map((u) => (u.id === id ? { ...u, progress: fraction } : u))),
      });
      // Functional: the author may have kept typing while this uploaded.
      update((s) => (s.files.some((f) => f.id === info.id) ? s : { ...s, files: [...s.files, info] }));
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return; // cancelled on purpose
      setError(`${file.name}: ${err instanceof ApiError ? err.message : "بارگذاری ناموفق بود."}`);
    } finally {
      setUploads((current) => current.filter((u) => u.id !== id));
      release?.();
    }
  }

  function handlePick(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = ""; // so picking the same file again still fires
    setError(null);
    files.forEach((file) => void upload(file));
  }

  return (
    <div className="space-y-5">
      <label className="block">
        <FieldLabel>عنوان</FieldLabel>
        <input
          type="text"
          value={section.heading}
          disabled={disabled}
          maxLength={500}
          placeholder={`${index}-توضیحات`}
          onChange={(event) => update((s) => ({ ...s, heading: event.target.value }))}
          className={inputClass}
        />
      </label>

      <div>
        <FieldLabel>متن</FieldLabel>
        <RichTextArea
          value={section.body}
          disabled={disabled}
          rows={8}
          onChange={(body) => update((s) => ({ ...s, body }))}
        />
      </div>

      {section.extra_boxes.map((box, position) => (
        <div key={position}>
          <div className="mb-1 flex items-center justify-between">
            <FieldLabel>کادر متن اضافه {position + 1}</FieldLabel>
            {!disabled && (
              <IconButton
                label="حذف این کادر"
                tone="danger"
                onClick={() =>
                  update((s) => ({ ...s, extra_boxes: s.extra_boxes.filter((_, i) => i !== position) }))
                }
              >
                <X />
              </IconButton>
            )}
          </div>
          <RichTextArea
            value={box}
            disabled={disabled}
            rows={5}
            onChange={(value) =>
              update((s) => ({ ...s, extra_boxes: s.extra_boxes.map((b, i) => (i === position ? value : b)) }))
            }
          />
        </div>
      ))}

      {!disabled && (
        <AddButton onClick={() => update((s) => ({ ...s, extra_boxes: [...s.extra_boxes, ""] }))}>
          افزودن کادر متن
        </AddButton>
      )}

      <div className="rounded-xl border border-slate-200 bg-slate-50/40 p-4">
        <FieldLabel>فایل‌های پیوست</FieldLabel>

        {!disabled && (
          <div className="mb-3 flex flex-wrap gap-2">
            {UPLOAD_BUTTONS.map(({ kind, label }) => (
              <span key={kind}>
                <input
                  ref={pickers[kind]}
                  type="file"
                  accept={ACCEPT[kind]}
                  multiple
                  hidden
                  onChange={handlePick}
                />
                <button
                  type="button"
                  onClick={() => pickers[kind].current?.click()}
                  className={buttonClass({ size: "sm" })}
                >
                  {label}
                </button>
              </span>
            ))}
          </div>
        )}

        {error && <p className="mb-2 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}

        {uploads.map((pending) => (
          <div key={pending.id} className="mb-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm">
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className="truncate">{pending.name}</span>
              <button
                type="button"
                onClick={() => pending.controller.abort()}
                className="shrink-0 text-xs text-rose-600 hover:underline"
              >
                لغو
              </button>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-slate-200">
              <div
                className="h-full rounded-full bg-brand-600 transition-[width] duration-300"
                style={{ width: `${Math.round(pending.progress * 100)}%` }}
              />
            </div>
          </div>
        ))}

        {section.files.length === 0 && uploads.length === 0 ? (
          <p className="text-sm text-slate-400">فایلی پیوست نشده است.</p>
        ) : (
          <ul className="space-y-2">
            {section.files.map((file) => (
              <FileRow
                key={file.id}
                name={file.name}
                href={file.download_url}
                size={file.size}
                kindLabel={file.kind_label}
                action={
                  !disabled && (
                    <IconButton
                      label="حذف فایل (با ذخیره‌سازی نهایی می‌شود)"
                      tone="danger"
                      onClick={() => update((s) => ({ ...s, files: s.files.filter((f) => f.id !== file.id) }))}
                    >
                      <X />
                    </IconButton>
                  )
                }
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
