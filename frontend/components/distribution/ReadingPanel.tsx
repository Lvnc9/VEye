"use client";

import { useState } from "react";
import { BookOpenCheck, Check, ChevronDown, CircleDashed, CircleCheck, Users } from "lucide-react";
import { ApiError } from "@/lib/api-client";
import { acknowledge, coverageLabel, type Coverage, type DocumentReading } from "@/lib/distribution";
import { formatJalali } from "@/lib/jalali";
import { useApiQuery } from "@/lib/use-api-query";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { SkeletonLines } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { cx } from "@/components/ui/cx";

/**
 * Read acknowledgment on the document itself (Phase 21): the «مطالعه کردم» prompt for someone the approved
 * revision was distributed to, and — for its authors and Reports holders — who has read it so far. Renders
 * nothing for anyone else, or for a document never distributed.
 */
export function ReadingPanel({ documentId, inForce }: { documentId: number; inForce: boolean }) {
  const toast = useToast();
  const [reload, setReload] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reading = useApiQuery<DocumentReading>(`/distribution/documents/${documentId}/`, reload);
  const data = reading.data;
  if (!data) return null;

  const mine = data.mine;
  const showCoverage = data.can_view_coverage && (data.total ?? 0) > 0;
  if (!mine && !showCoverage) return null;

  async function done() {
    setSaving(true);
    setError(null);
    try {
      await acknowledge(documentId);
      toast({ tone: "success", title: "مطالعهٔ شما ثبت شد." });
      setReload((n) => n + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ثبت مطالعه ممکن نشد.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      {mine && !mine.acknowledged_at && inForce && (
        <Alert
          tone="info"
          role="status"
          title="این مستند برای مطالعهٔ شما ابلاغ شده است."
          actions={
            <Button size="sm" variant="primary" icon={<Check />} loading={saving} onClick={() => void done()}>
              مطالعه کردم
            </Button>
          }
        >
          پس از خواندن متن کامل (دکمهٔ «نمایش»)، مطالعهٔ خود را ثبت کنید.
          {error && <span className="block text-destructive">{error}</span>}
        </Alert>
      )}
      {mine?.acknowledged_at && (
        <p className="flex items-center gap-2 text-sm text-success">
          <BookOpenCheck className="size-4" />
          مطالعهٔ شما در {formatJalali(mine.acknowledged_at)} ثبت شده است.
        </p>
      )}
      {showCoverage && <CoverageCard documentId={documentId} reading={data} reload={reload} />}
    </div>
  );
}

function CoverageCard({ documentId, reading, reload }: { documentId: number; reading: DocumentReading; reload: number }) {
  const [open, setOpen] = useState(false);
  const percent = reading.total ? Math.round((100 * (reading.acknowledged ?? 0)) / reading.total) : null;
  return (
    <Card aria-label="پوشش مطالعه">
      <CardHeader
        title="پوشش مطالعه"
        icon={<Users />}
        description="کسانی که این بازنگری به آن‌ها ابلاغ شد (گرهٔ مالک و واحدهای مسئول، هنگام تصویب)"
        actions={
          <Button size="sm" variant="ghost" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
            <ChevronDown className={cx("transition-transform", open && "rotate-180")} />
            {open ? "بستن فهرست" : "فهرست افراد"}
          </Button>
        }
      />
      <div className="flex flex-wrap items-center gap-3">
        <ProgressBar value={percent} label="درصد مطالعه" className="min-w-[10rem] flex-1" />
        <span className="text-sm text-soft-foreground tabular-nums">{coverageLabel(reading.acknowledged, reading.total)}</span>
      </div>
      {open && <CoverageList documentId={documentId} reload={reload} />}
    </Card>
  );
}

function CoverageList({ documentId, reload }: { documentId: number; reload: number }) {
  const coverage = useApiQuery<Coverage>(`/distribution/documents/${documentId}/coverage/`, reload);
  if (coverage.loading && !coverage.data) return <SkeletonLines rows={3} />;
  if (coverage.error) return <p className="mt-3 text-sm text-destructive">{coverage.error}</p>;
  if (!coverage.data) return null;
  return (
    <div className="mt-4 space-y-4">
      {coverage.data.groups.map((group) => (
        <section key={group.node_name || "—"}>
          <h3 className="mb-2 text-xs font-bold text-muted-foreground">{group.node_name || "بدون جایگاه"}</h3>
          <ul className="grid gap-1.5 sm:grid-cols-2">
            {group.people.map((person) => (
              <li key={`${group.node_name}:${person.name}`} className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-accent">
                {person.acknowledged_at ? (
                  <CircleCheck className="size-4 shrink-0 text-success" aria-label="مطالعه کرده" />
                ) : (
                  <CircleDashed className="size-4 shrink-0 text-subtle-foreground" aria-label="هنوز نه" />
                )}
                <span className="min-w-0 flex-1 truncate text-foreground">{person.name}</span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {person.acknowledged_at ? formatJalali(person.acknowledged_at) : "هنوز نه"}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
