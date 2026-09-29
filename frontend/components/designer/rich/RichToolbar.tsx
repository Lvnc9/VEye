"use client";

import { useState, type ReactNode } from "react";
import { useEditorState, type Editor } from "@tiptap/react";
import {
  AlignCenter,
  AlignJustify,
  AlignLeft,
  AlignRight,
  Bold,
  FilePlus2,
  IndentDecrease,
  IndentIncrease,
  Italic,
  Link2,
  List,
  ListOrdered,
  Minus,
  Palette,
  Redo2,
  RemoveFormatting,
  Strikethrough,
  Table2,
  Underline,
  Undo2,
} from "lucide-react";
import { Dialog } from "@/components/ui/Dialog";
import { Field, inputClass, selectClass } from "@/components/ui/Field";
import { Popover } from "@/components/ui/Popover";
import { buttonClass } from "@/components/ui/Button";
import { cx } from "@/components/ui/cx";
import {
  FONT_SIZES,
  MAX_INDENT,
  MAX_LIST_DEPTH,
  MAX_TABLE_COLUMNS,
  MAX_TABLE_ROWS,
  PALETTE,
  isAllowedLink,
} from "@/lib/rich-doc";

type Align = "right" | "center" | "left" | "justify";

interface ToolbarState {
  bold: boolean;
  italic: boolean;
  underline: boolean;
  strike: boolean;
  align: Align;
  block: "p" | "1" | "2" | "3";
  fontSize: number | null;
  color: string | null;
  bullet: boolean;
  ordered: boolean;
  inList: boolean;
  inTable: boolean;
  listDepth: number;
  indent: number;
  rows: number;
  columns: number;
  hasHeaderRow: boolean;
  link: string | null;
  selectionEmpty: boolean;
  canUndo: boolean;
  canRedo: boolean;
}

function readState(editor: Editor): ToolbarState {
  const { $from, empty } = editor.state.selection;
  let listDepth = 0;
  let table: { rows: number; columns: number; header: boolean } | null = null;
  for (let depth = $from.depth; depth > 0; depth -= 1) {
    const node = $from.node(depth);
    if (node.type.name === "bulletList" || node.type.name === "orderedList") listDepth += 1;
    if (node.type.name === "table" && !table) {
      const first = node.firstChild;
      table = {
        rows: node.childCount,
        columns: first ? first.childCount : 0,
        header: first?.firstChild?.type.name === "tableHeader",
      };
    }
  }
  const heading = editor.isActive("heading") ? editor.getAttributes("heading") : null;
  const block = heading ? (String(heading.level) as "1" | "2" | "3") : "p";
  const attrs = heading ?? editor.getAttributes("paragraph");
  return {
    bold: editor.isActive("bold"),
    italic: editor.isActive("italic"),
    underline: editor.isActive("underline"),
    strike: editor.isActive("strike"),
    align: (attrs.textAlign as Align | null) ?? "right",
    block,
    fontSize: (editor.getAttributes("textStyle").fontSize as number | null) ?? null,
    color: (editor.getAttributes("textStyle").color as string | null) ?? null,
    bullet: editor.isActive("bulletList"),
    ordered: editor.isActive("orderedList"),
    inList: editor.isActive("listItem"),
    inTable: table !== null,
    listDepth,
    indent: Number(attrs.indent ?? 0),
    rows: table?.rows ?? 0,
    columns: table?.columns ?? 0,
    hasHeaderRow: table?.header ?? false,
    link: (editor.getAttributes("link").href as string | null) ?? null,
    selectionEmpty: empty,
    canUndo: editor.can().undo(),
    canRedo: editor.can().redo(),
  };
}

const buttonBase =
  "inline-flex size-9 shrink-0 items-center justify-center rounded-lg text-slate-600 transition-colors " +
  "hover:bg-slate-100 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:bg-transparent " +
  "pointer-coarse:size-11 [&_svg]:size-[18px]";
const buttonActive = "bg-brand-50 text-brand-800 hover:bg-brand-100 hover:text-brand-900";

function ToolButton({
  label,
  active,
  disabled,
  onClick,
  children,
}: {
  label: string;
  active?: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      aria-pressed={active}
      disabled={disabled}
      // A button that took focus would collapse the editor's selection before the command ran.
      onMouseDown={(event) => event.preventDefault()}
      onClick={onClick}
      className={cx(buttonBase, active && buttonActive)}
    >
      {children}
    </button>
  );
}

function Divider() {
  return <span aria-hidden className="mx-1 hidden h-6 w-px bg-slate-200 sm:inline-block" />;
}

function MenuItem({ children, disabled, onClick }: { children: ReactNode; disabled?: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onMouseDown={(event) => event.preventDefault()}
      onClick={onClick}
      className="flex w-full items-center rounded-lg px-3 py-2 text-start text-sm text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent"
    >
      {children}
    </button>
  );
}

/** Indent: inside a list it nests (or un-nests) the item; elsewhere it moves the paragraph in steps. */
function changeIndent(editor: Editor, state: ToolbarState, delta: 1 | -1) {
  if (state.inList) {
    if (delta > 0 && state.listDepth < MAX_LIST_DEPTH) editor.chain().focus().sinkListItem("listItem").run();
    if (delta < 0) editor.chain().focus().liftListItem("listItem").run();
    return;
  }
  const type = editor.isActive("heading") ? "heading" : "paragraph";
  const next = Math.min(Math.max(state.indent + delta, 0), MAX_INDENT);
  editor.chain().focus().updateAttributes(type, { indent: next }).run();
}

export function RichToolbar({ editor }: { editor: Editor }) {
  const state = useEditorState({ editor, selector: ({ editor: current }) => readState(current) });
  const [linkOpen, setLinkOpen] = useState(false);
  const blocked = state.inList || state.inTable; // where a table, rule or page break cannot go

  const align: { value: Align; label: string; icon: ReactNode }[] = [
    { value: "right", label: "راست‌چین", icon: <AlignRight /> },
    { value: "center", label: "وسط‌چین", icon: <AlignCenter /> },
    { value: "left", label: "چپ‌چین", icon: <AlignLeft /> },
    { value: "justify", label: "تراز دوطرفه", icon: <AlignJustify /> },
  ];

  return (
    <div
      role="toolbar"
      aria-label="ابزار قالب‌بندی متن"
      className="z-20 flex flex-wrap items-center gap-0.5 rounded-t-xl border-b border-slate-200 bg-white/95 px-2 py-1.5 backdrop-blur md:sticky md:top-0"
    >
      <ToolButton label="واگرد (Ctrl+Z)" disabled={!state.canUndo} onClick={() => editor.chain().focus().undo().run()}>
        <Undo2 />
      </ToolButton>
      <ToolButton label="ازنو (Ctrl+Shift+Z)" disabled={!state.canRedo} onClick={() => editor.chain().focus().redo().run()}>
        <Redo2 />
      </ToolButton>
      <Divider />

      <select
        aria-label="سبک بند"
        title="سبک بند"
        value={state.block}
        disabled={state.inList}
        onChange={(event) => {
          const value = event.target.value;
          const chain = editor.chain().focus();
          if (value === "p") chain.setParagraph().run();
          else chain.setHeading({ level: Number(value) as 1 | 2 | 3 }).run();
        }}
        className={cx(selectClass, "h-9 w-28 px-2 pointer-coarse:h-11")}
      >
        <option value="p">متن عادی</option>
        <option value="1">عنوان ۱</option>
        <option value="2">عنوان ۲</option>
        <option value="3">عنوان ۳</option>
      </select>
      <select
        aria-label="اندازهٔ قلم"
        title="اندازهٔ قلم (پوینت)"
        value={state.fontSize ?? ""}
        onChange={(event) => {
          const value = event.target.value;
          const chain = editor.chain().focus();
          if (value === "") chain.setMark("textStyle", { fontSize: null }).removeEmptyTextStyle().run();
          else chain.setMark("textStyle", { fontSize: Number(value) }).run();
        }}
        className={cx(selectClass, "h-9 w-24 px-2 pointer-coarse:h-11")}
      >
        <option value="">پیش‌فرض</option>
        {FONT_SIZES.map((size) => (
          <option key={size} value={size}>
            {size}
          </option>
        ))}
      </select>
      <Divider />

      <ToolButton label="پررنگ (Ctrl+B)" active={state.bold} onClick={() => editor.chain().focus().toggleBold().run()}>
        <Bold />
      </ToolButton>
      <ToolButton label="مایل (Ctrl+I)" active={state.italic} onClick={() => editor.chain().focus().toggleItalic().run()}>
        <Italic />
      </ToolButton>
      <ToolButton label="زیرخط (Ctrl+U)" active={state.underline} onClick={() => editor.chain().focus().toggleUnderline().run()}>
        <Underline />
      </ToolButton>
      <ToolButton label="خط‌خورده" active={state.strike} onClick={() => editor.chain().focus().toggleStrike().run()}>
        <Strikethrough />
      </ToolButton>
      <Popover
        label="رنگ متن"
        trigger={
          <span className="relative flex flex-col items-center">
            <Palette />
            <span
              aria-hidden
              className="absolute -bottom-1 h-[3px] w-4 rounded-full"
              style={{ backgroundColor: state.color ?? "#000000" }}
            />
          </span>
        }
        triggerClassName={buttonBase}
        panelClassName="w-48"
      >
        {(close) => (
          <div className="space-y-2">
            <div className="grid grid-cols-7 gap-1.5">
              {PALETTE.map((color) => (
                <button
                  key={color.value}
                  type="button"
                  aria-label={color.label}
                  title={color.label}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => {
                    editor.chain().focus().setMark("textStyle", { color: color.value }).run();
                    close();
                  }}
                  className={cx(
                    "size-6 rounded-full border border-black/10 transition-transform hover:scale-110 pointer-coarse:size-8",
                    state.color === color.value && "ring-2 ring-brand-500 ring-offset-1",
                  )}
                  style={{ backgroundColor: color.value }}
                />
              ))}
            </div>
            <MenuItem
              onClick={() => {
                editor.chain().focus().setMark("textStyle", { color: null }).removeEmptyTextStyle().run();
                close();
              }}
            >
              رنگ پیش‌فرض
            </MenuItem>
          </div>
        )}
      </Popover>
      <Divider />

      {align.map((item) => (
        <ToolButton
          key={item.value}
          label={item.label}
          active={state.align === item.value}
          onClick={() => editor.chain().focus().setTextAlign(item.value).run()}
        >
          {item.icon}
        </ToolButton>
      ))}
      <Divider />

      <ToolButton label="فهرست نقطه‌ای" active={state.bullet} onClick={() => editor.chain().focus().toggleBulletList().run()}>
        <List />
      </ToolButton>
      <ToolButton label="فهرست شماره‌دار" active={state.ordered} onClick={() => editor.chain().focus().toggleOrderedList().run()}>
        <ListOrdered />
      </ToolButton>
      <ToolButton
        label="افزایش تورفتگی"
        disabled={state.inList ? state.listDepth >= MAX_LIST_DEPTH : state.indent >= MAX_INDENT}
        onClick={() => changeIndent(editor, state, 1)}
      >
        <IndentIncrease className="-scale-x-100" />
      </ToolButton>
      <ToolButton
        label="کاهش تورفتگی"
        disabled={state.inList ? false : state.indent <= 0}
        onClick={() => changeIndent(editor, state, -1)}
      >
        <IndentDecrease className="-scale-x-100" />
      </ToolButton>
      <Divider />

      <ToolButton label="پیوند (نشانی اینترنتی)" active={state.link !== null} onClick={() => setLinkOpen(true)}>
        <Link2 />
      </ToolButton>
      <Popover label="جدول" trigger={<Table2 />} triggerClassName={cx(buttonBase, state.inTable && buttonActive)} panelClassName="w-60">
        {(close) => {
          const run = (command: () => boolean) => () => {
            command();
            close();
          };
          const chain = () => editor.chain().focus();
          return (
            <div className="space-y-0.5">
              <MenuItem
                disabled={blocked}
                onClick={run(() => chain().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run())}
              >
                درج جدول ۳×۳
              </MenuItem>
              <MenuItem disabled={!state.inTable || state.columns >= MAX_TABLE_COLUMNS} onClick={run(() => chain().addColumnAfter().run())}>
                افزودن ستون بعد از این
              </MenuItem>
              <MenuItem disabled={!state.inTable || state.columns >= MAX_TABLE_COLUMNS} onClick={run(() => chain().addColumnBefore().run())}>
                افزودن ستون قبل از این
              </MenuItem>
              <MenuItem disabled={!state.inTable || state.columns <= 1} onClick={run(() => chain().deleteColumn().run())}>
                حذف ستون
              </MenuItem>
              <MenuItem disabled={!state.inTable || state.rows >= MAX_TABLE_ROWS} onClick={run(() => chain().addRowAfter().run())}>
                افزودن سطر بعد از این
              </MenuItem>
              <MenuItem disabled={!state.inTable || state.rows >= MAX_TABLE_ROWS} onClick={run(() => chain().addRowBefore().run())}>
                افزودن سطر قبل از این
              </MenuItem>
              <MenuItem disabled={!state.inTable || state.rows <= 1} onClick={run(() => chain().deleteRow().run())}>
                حذف سطر
              </MenuItem>
              <MenuItem disabled={!state.inTable} onClick={run(() => chain().toggleHeaderRow().run())}>
                {state.hasHeaderRow ? "برداشتن سطر عنوان" : "سطر اول عنوان باشد"}
              </MenuItem>
              <MenuItem disabled={!state.inTable} onClick={run(() => chain().deleteTable().run())}>
                <span className="text-rose-700">حذف جدول</span>
              </MenuItem>
            </div>
          );
        }}
      </Popover>
      <ToolButton label="خط جداکننده" disabled={blocked} onClick={() => editor.chain().focus().setHorizontalRule().run()}>
        <Minus />
      </ToolButton>
      <ToolButton
        label="شکست صفحه (ادامه از صفحهٔ بعد)"
        disabled={blocked}
        // The paragraph after it is where typing continues (an atom block cannot hold the cursor).
        onClick={() => editor.chain().focus().insertContent([{ type: "pageBreak" }, { type: "paragraph" }]).run()}
      >
        <FilePlus2 />
      </ToolButton>
      <ToolButton label="پاک کردن قالب‌بندی متن" onClick={() => editor.chain().focus().unsetAllMarks().run()}>
        <RemoveFormatting />
      </ToolButton>

      {linkOpen && (
        <LinkDialog
          initial={state.link ?? ""}
          hasLink={state.link !== null}
          selectionEmpty={state.selectionEmpty}
          onClose={() => {
            setLinkOpen(false);
            editor.commands.focus();
          }}
          onSave={(href) => {
            const chain = editor.chain().focus();
            if (state.link !== null) chain.extendMarkRange("link").setLink({ href }).run();
            else if (state.selectionEmpty)
              chain.insertContent({ type: "text", text: href, marks: [{ type: "link", attrs: { href } }] }).run();
            else chain.setLink({ href }).run();
            setLinkOpen(false);
          }}
          onRemove={() => {
            editor.chain().focus().extendMarkRange("link").unsetLink().run();
            setLinkOpen(false);
          }}
        />
      )}
    </div>
  );
}

function LinkDialog({
  initial,
  hasLink,
  selectionEmpty,
  onClose,
  onSave,
  onRemove,
}: {
  initial: string;
  hasLink: boolean;
  selectionEmpty: boolean;
  onClose: () => void;
  onSave: (href: string) => void;
  onRemove: () => void;
}) {
  const [href, setHref] = useState(initial);
  const [error, setError] = useState<string | null>(null);

  function submit() {
    const value = href.trim();
    if (!isAllowedLink(value)) {
      setError("نشانی باید با http://‎ یا https://‎ یا mailto: شروع شود و فاصله نداشته باشد.");
      return;
    }
    onSave(value);
  }

  return (
    <Dialog label="پیوند" title="پیوند به نشانی اینترنتی" onClose={onClose} size="md"
      description={
        hasLink
          ? "نشانی این پیوند را ویرایش کنید."
          : selectionEmpty
            ? "نشانی وارد شده به‌صورت پیوند در متن درج می‌شود. لینک فایل پیوست را هم می‌توانید همین‌جا جایگذاری کنید."
            : "متن انتخاب‌شده به این نشانی پیوند می‌خورد."
      }
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
        className="space-y-4"
      >
        <Field label="نشانی" htmlFor="rich-link-url" error={error}>
          <input
            id="rich-link-url"
            type="url"
            dir="ltr"
            autoFocus
            value={href}
            onChange={(event) => {
              setHref(event.target.value);
              setError(null);
            }}
            placeholder="https://"
            className={inputClass}
          />
        </Field>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex gap-2">
            <button type="submit" className={buttonClass({ variant: "primary" })}>
              ثبت پیوند
            </button>
            <button type="button" onClick={onClose} className={buttonClass()}>
              انصراف
            </button>
          </div>
          {hasLink && (
            <button type="button" onClick={onRemove} className={buttonClass({ variant: "danger-ghost" })}>
              حذف پیوند
            </button>
          )}
        </div>
      </form>
    </Dialog>
  );
}
