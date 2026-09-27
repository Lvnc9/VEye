import type { ReactNode } from "react";
import { formatSize } from "@/lib/file-size";

export { formatSize };

/**
 * One stored file in a list: its name as a download link, then its kind label, size and an optional
 * action (a remove button). Shared by the designer's تشریحی بلند block and کارتابل messages.
 * `tone="dark"` is for a file inside the sender's own (dark) chat bubble.
 */
export function FileRow({
  name,
  href,
  size,
  kindLabel,
  action,
  tone = "light",
}: {
  name: string;
  href: string;
  size: number;
  kindLabel?: string;
  action?: ReactNode;
  tone?: "light" | "dark";
}) {
  const dark = tone === "dark";
  return (
    <li
      className={`flex items-center justify-between gap-2 rounded border px-3 py-2 text-sm ${
        dark ? "border-slate-600 bg-slate-800" : "border-slate-200 bg-slate-50"
      }`}
    >
      <a
        href={href}
        target="_blank"
        rel="noreferrer"
        className={`min-w-0 truncate font-medium underline ${
          dark
            ? "text-white decoration-slate-400 hover:decoration-white"
            : "text-slate-800 decoration-slate-300 hover:decoration-slate-600"
        }`}
        title={name}
      >
        {name}
      </a>
      <span className={`flex shrink-0 items-center gap-2 text-xs ${dark ? "text-slate-300" : "text-slate-500"}`}>
        {kindLabel && <span>{kindLabel}</span>}
        <bdi dir="ltr">{formatSize(size)}</bdi>
        {action}
      </span>
    </li>
  );
}
