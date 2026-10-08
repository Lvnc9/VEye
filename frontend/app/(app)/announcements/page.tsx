"use client";

import { useState } from "react";
import { Archive, Megaphone, Pencil, Pin, PinOff, Plus, Trash2 } from "lucide-react";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { AnnouncementCard } from "@/components/announcements/AnnouncementCard";
import { AnnouncementFormDialog } from "@/components/announcements/AnnouncementFormDialog";
import { Pager } from "@/components/Pager";
import { ErrorBanner } from "@/components/StatusBanner";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { SkeletonLines } from "@/components/ui/Skeleton";
import { ApiError, apiPatch, apiPost } from "@/lib/api-client";
import { canPublish, type Announcement } from "@/lib/announcements";
import { useCurrentUser } from "@/lib/current-user";
import { usePagedQuery } from "@/lib/use-paged-query";

const PAGE_SIZE = 10;

type Dialog = { kind: "new" } | { kind: "edit" | "withdraw"; announcement: Announcement } | null;

/** «اطلاعیه‌ها» (Phase 19): the notices meant for the viewer — the company's and those of the units they sit
 *  in or lead — pinned first. HR publishes to the company, a مسئول to their unit; the buttons on each notice
 *  are the ones the server allows (`can_manage`). Past and withdrawn notices are in «بایگانی». */
export default function AnnouncementsPage() {
  const { user, can } = useCurrentUser();
  const [archive, setArchive] = useState(false);
  const [page, setPage] = useState(1);
  const [reload, setReload] = useState(0);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [error, setError] = useState<string | null>(null);
  const { rows, count, error: loadError, loading } = usePagedQuery<Announcement>(
    "/announcements/",
    archive ? { page, page_size: PAGE_SIZE, archive: 1 } : { page, page_size: PAGE_SIZE },
    reload,
  );
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));
  const done = () => {
    setDialog(null);
    setError(null);
    setReload((n) => n + 1);
  };

  async function togglePin(announcement: Announcement) {
    setError(null);
    try {
      await apiPatch(`/announcements/${announcement.id}/`, { pinned: !announcement.pinned });
      setReload((n) => n + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تغییر ممکن نشد.");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="اطلاعیه‌ها"
        subtitle="اطلاعیه‌های سازمان و واحدهایی که در آن‌ها هستید"
        actions={
          <>
            <Button
              variant="ghost"
              icon={<Archive />}
              aria-pressed={archive}
              onClick={() => {
                setArchive((a) => !a);
                setPage(1);
              }}
            >
              {archive ? "اطلاعیه‌های جاری" : "بایگانی"}
            </Button>
            {canPublish(can("manage_personnel"), user?.memberships) && (
              <Button variant="primary" icon={<Plus />} onClick={() => setDialog({ kind: "new" })}>
                انتشار اطلاعیه
              </Button>
            )}
          </>
        }
      />
      {error && <ErrorBanner message={error} />}

      {loading ? (
        <SkeletonLines rows={4} />
      ) : loadError ? (
        <ErrorBanner message={loadError} />
      ) : rows.length === 0 ? (
        <EmptyState icon={<Megaphone />} message={archive ? "بایگانی خالی است." : "اطلاعیهٔ جاری‌ای نیست."} />
      ) : (
        <div className="space-y-4">
          {rows.map((announcement) => (
            <AnnouncementCard
              key={announcement.id}
              announcement={announcement}
              actions={
                announcement.can_manage && (
                  <>
                    <Button size="sm" icon={<Pencil />} onClick={() => setDialog({ kind: "edit", announcement })}>
                      ویرایش
                    </Button>
                    <Button size="sm" icon={announcement.pinned ? <PinOff /> : <Pin />} onClick={() => togglePin(announcement)}>
                      {announcement.pinned ? "برداشتن سنجاق" : "سنجاق"}
                    </Button>
                    <Button size="sm" variant="ghost" icon={<Trash2 />} onClick={() => setDialog({ kind: "withdraw", announcement })}>
                      برداشتن اطلاعیه
                    </Button>
                  </>
                )
              }
            />
          ))}
        </div>
      )}

      <Pager page={page} totalPages={totalPages} onChange={setPage} />

      {dialog?.kind === "new" && <AnnouncementFormDialog onSaved={done} onClose={() => setDialog(null)} />}
      {dialog?.kind === "edit" && <AnnouncementFormDialog announcement={dialog.announcement} onSaved={done} onClose={() => setDialog(null)} />}
      {dialog?.kind === "withdraw" && (
        <ConfirmDialog
          title="برداشتن اطلاعیه"
          message="اطلاعیه از فهرست همه برداشته می‌شود و فقط کسانی که آن را مدیریت می‌کنند در بایگانی می‌بینندش. این کار برگشت‌پذیر نیست."
          confirmLabel="برداشتن"
          danger
          onConfirm={async () => {
            await apiPost(`/announcements/${dialog.announcement.id}/withdraw/`);
            done();
          }}
          onCancel={() => setDialog(null)}
        />
      )}
    </div>
  );
}
