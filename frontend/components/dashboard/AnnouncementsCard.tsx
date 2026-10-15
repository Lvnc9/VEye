"use client";

import Link from "next/link";
import { Megaphone, Pin } from "lucide-react";
import { Card, CardHeader } from "@/components/ui/Card";
import { excerpt, type Announcement } from "@/lib/announcements";
import { formatJalali } from "@/lib/jalali";
import type { Paginated } from "@/lib/types";
import { useApiQuery } from "@/lib/use-api-query";

/** The three latest current announcements for the viewer, on the dashboard. Nothing at all when there are
 *  none (an empty card would be noise); a failure is silent for the same reason — the page has its own. */
export function AnnouncementsCard() {
  const latest = useApiQuery<Paginated<Announcement>>("/announcements/?page_size=3");
  const rows = latest.data?.results ?? [];
  if (rows.length === 0) return null;
  return (
    <Card aria-label="اطلاعیه‌ها">
      <CardHeader
        title="اطلاعیه‌ها"
        icon={<Megaphone />}
        actions={
          <Link href="/announcements" className="text-xs text-primary hover:underline">
            همهٔ اطلاعیه‌ها
          </Link>
        }
      />
      <ul className="space-y-3">
        {rows.map((a) => (
          <li key={a.id} className="rounded-xl bg-muted/50 px-3 py-2.5 ring-1 ring-inset ring-border">
            <Link href="/announcements" className="block">
              <p className="flex items-center gap-1.5 text-sm font-bold text-foreground">
                {a.pinned && <Pin className="size-3.5 shrink-0 text-primary" aria-label="سنجاق‌شده" />}
                {a.title}
              </p>
              <p className="mt-1 text-xs leading-6 text-soft-foreground">{excerpt(a.body, 140)}</p>
              <p className="mt-1 text-[11px] text-muted-foreground">
                {a.audience_name} · {a.author_name} · {formatJalali(a.created_at)}
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}
