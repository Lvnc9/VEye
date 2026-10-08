import type { ReactNode } from "react";
import { Pin, Users } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { cardClass } from "@/components/ui/Card";
import { cx } from "@/components/ui/cx";
import { formatJalali } from "@/lib/jalali";
import type { Announcement } from "@/lib/announcements";

/** One announcement as people read it: title, who it is for, who said it and when, and the text with its
 *  line breaks kept. `actions` are the manage buttons, when the viewer may manage it. */
export function AnnouncementCard({ announcement, actions }: { announcement: Announcement; actions?: ReactNode }) {
  return (
    <article className={cx(cardClass, "p-5 sm:p-6", announcement.pinned && !announcement.is_withdrawn && "ring-1 ring-brand-300")}>
      <header className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 text-lg font-bold leading-8 text-slate-900">
            {announcement.pinned && <Pin className="size-4 shrink-0 text-brand-600" aria-label="سنجاق‌شده" />}
            {announcement.title}
          </h2>
          <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
            <span className="inline-flex items-center gap-1">
              <Users className="size-3.5" />
              {announcement.audience_name}
            </span>
            <span>
              {announcement.author_name} · {formatJalali(announcement.created_at)}
            </span>
            {announcement.edited_at && <span>ویرایش‌شده</span>}
            {announcement.expires_on && <span>نمایش تا {formatJalali(announcement.expires_on)}</span>}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {announcement.is_withdrawn && <Badge tone="neutral">برداشته‌شده</Badge>}
          {!announcement.is_withdrawn && announcement.is_expired && <Badge tone="neutral">پایان‌یافته</Badge>}
        </div>
      </header>
      <p className="whitespace-pre-line text-sm leading-8 text-slate-800">{announcement.body}</p>
      {actions && <div className="mt-4 flex flex-wrap gap-2 border-t border-slate-100 pt-3">{actions}</div>}
    </article>
  );
}
