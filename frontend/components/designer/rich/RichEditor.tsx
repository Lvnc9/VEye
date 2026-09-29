"use client";

import { useEffect, useMemo, useRef } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import { cx } from "@/components/ui/cx";
import type { RichDoc } from "@/lib/rich-doc";
import { richExtensions } from "./extensions";
import { RichToolbar } from "./RichToolbar";

/**
 * The Word-like body of a تشریحی بلند block (owner's request, 2026-09-29).
 *
 * `value` is the block's stored document, or null while a legacy block has not been edited yet — the
 * editor then shows `fallback` (the old marker text converted) and reports nothing until the user
 * changes something, so an untouched block keeps printing the old way.
 *
 * Text is edited in the editor's own history (Ctrl/⌘+Z inside it undoes typing); the designer's
 * document undo also reaches here through `value`, which is written back into the editor when it
 * was changed from outside.
 */
export function RichEditor({
  value,
  fallback,
  onChange,
  disabled,
  label = "متن",
}: {
  value: RichDoc | null;
  fallback: RichDoc;
  onChange: (value: RichDoc) => void;
  disabled?: boolean;
  label?: string;
}) {
  const extensions = useMemo(() => richExtensions(), []);
  const shown = value ?? fallback;
  // The JSON the editor was last known to hold — what it emitted or was given.
  const known = useRef(JSON.stringify(shown.doc));
  const onChangeRef = useRef(onChange);
  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  const editor = useEditor({
    extensions,
    content: shown.doc,
    editable: !disabled,
    // Next renders this on the server first; Tiptap would otherwise mismatch on hydration.
    immediatelyRender: false,
    editorProps: {
      attributes: { dir: "rtl", role: "textbox", "aria-multiline": "true", "aria-label": label, class: "rich-content" },
    },
    onUpdate: ({ editor: current, transaction }) => {
      // `setEditable` and the like report an update without touching the document.
      if (!transaction.docChanged) return;
      const doc = current.getJSON();
      known.current = JSON.stringify(doc);
      onChangeRef.current({ v: 1, doc: doc as RichDoc["doc"] });
    },
  });

  useEffect(() => {
    editor?.setEditable(!disabled, false);
  }, [editor, disabled]);

  // The document changed from outside (the designer's undo/redo, a restored draft): show it.
  const incoming = JSON.stringify(shown.doc);
  useEffect(() => {
    if (!editor || incoming === known.current) return;
    editor.commands.setContent(shown.doc, { emitUpdate: false });
    known.current = incoming;
    // `shown.doc` is what `incoming` was made from.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editor, incoming]);

  return (
    <div className={cx("rich-editor rounded-xl border border-slate-300 bg-white shadow-xs", disabled && "bg-slate-50")}>
      {editor && !disabled && <RichToolbar editor={editor} />}
      <EditorContent editor={editor} className="rich-scroll" />
    </div>
  );
}
