import type { ReactNode } from "react";
import { FileText } from "lucide-react";
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
      className={`flex items-center justify-between gap-2 rounded-xl border px-3 py-2 text-sm transition-colors ${
        dark ? "border-white/15 bg-white/10" : "border-slate-200 bg-white hover:border-slate-300"
      }`}
    >
      <FileText className={`size-4 ${dark ? "text-white/70" : "text-brand-600"}`} />
      <a
        href={href}
        target="_blank"
        rel="noreferrer"
        className={`min-w-0 flex-1 truncate underline-offset-4 hover:underline ${
          dark ? "text-white decoration-white/60" : "text-slate-800 decoration-slate-400"
        }`}
        title={name}
      >
        {name}
      </a>
      <span className={`flex shrink-0 items-center gap-2 text-xs ${dark ? "text-white/70" : "text-slate-500"}`}>
        {kindLabel && <span>{kindLabel}</span>}
        <bdi dir="ltr">{formatSize(size)}</bdi>
        {action}
      </span>
    </li>
  );
}
