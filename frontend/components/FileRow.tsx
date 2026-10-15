import type { ReactNode } from "react";
import { Download, FileText, Link2 } from "lucide-react";
import { formatSize } from "@/lib/file-size";

export { formatSize };

/**
 * One stored file in a list: its name as a download link, then its kind label, size and an optional
 * action (a remove button). Shared by the designer's تشریحی بلند block and کارتابل messages.
 * `tone="dark"` is for a file inside the sender's own (dark) chat bubble.
 * With `onCopyLink` the name is a button that copies the file's link (the designer's list); the
 * download stays one click away as a small icon. Without it the name is the download link.
 */
export function FileRow({
  name,
  href,
  size,
  kindLabel,
  action,
  tone = "light",
  onCopyLink,
}: {
  name: string;
  href: string;
  size: number;
  kindLabel?: string;
  action?: ReactNode;
  tone?: "light" | "dark";
  onCopyLink?: () => void;
}) {
  const dark = tone === "dark";
  return (
    <li
      className={`flex items-center justify-between gap-2 rounded-xl border px-3 py-2 text-sm transition-colors ${
        dark ? "border-white/15 bg-white/10" : "border-border bg-card hover:border-input"
      }`}
    >
      <FileText className={`size-4 ${dark ? "text-white/70" : "text-primary"}`} />
      {onCopyLink ? (
        <button
          type="button"
          onClick={onCopyLink}
          className={`flex min-w-0 flex-1 items-center gap-1.5 rounded-md text-start underline-offset-4 hover:underline ${
            dark ? "text-white decoration-white/60" : "text-foreground decoration-slate-400"
          }`}
          title={`کپی لینک «${name}»`}
        >
          <span className="min-w-0 truncate">{name}</span>
          <Link2 aria-hidden className={`size-3.5 shrink-0 ${dark ? "text-white/70" : "text-subtle-foreground"}`} />
        </button>
      ) : (
        <a
          href={href}
          target="_blank"
          rel="noreferrer"
          className={`min-w-0 flex-1 truncate underline-offset-4 hover:underline ${
            dark ? "text-white decoration-white/60" : "text-foreground decoration-slate-400"
          }`}
          title={name}
        >
          {name}
        </a>
      )}
      <span className={`flex shrink-0 items-center gap-2 text-xs ${dark ? "text-white/70" : "text-muted-foreground"}`}>
        {kindLabel && <span>{kindLabel}</span>}
        <bdi dir="ltr">{formatSize(size)}</bdi>
        {onCopyLink && (
          <a
            href={href}
            target="_blank"
            rel="noreferrer"
            aria-label={`دریافت فایل «${name}»`}
            title="دریافت فایل"
            className="inline-flex size-7 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <Download className="size-4" />
          </a>
        )}
        {action}
      </span>
    </li>
  );
}
