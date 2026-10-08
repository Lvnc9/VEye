"use client";

import { useMemo, useState } from "react";
import { ApiError, apiPatch, apiPost } from "@/lib/api-client";
import {
  BODY_MAX,
  TITLE_MAX,
  announcementPatchPayload,
  announcementPayload,
  audienceChoices,
  emptyAnnouncementForm,
  formFromAnnouncement,
  validateAnnouncementForm,
  type Announcement,
  type AnnouncementForm,
} from "@/lib/announcements";
import { useCurrentUser } from "@/lib/current-user";
import { todayIso } from "@/lib/jalali";
import { nodeOptions, type OrgTreeResponse } from "@/lib/organization";
import { useApiQuery } from "@/lib/use-api-query";
import { JalaliDatePicker } from "@/components/JalaliDatePicker";
import { ErrorBanner } from "@/components/StatusBanner";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogFooter } from "@/components/ui/Dialog";
import { Field, inputClass, selectClass, textareaClass } from "@/components/ui/Field";

/**
 * Publish an announcement — or, with `announcement`, change its words, pin or end date (its audience is
 * fixed once published, so the audience picker is shown only when publishing). The audiences offered are the
 * server's rule: the whole company and every node for HR, a مسئول's own node and what is beneath it.
 */
export function AnnouncementFormDialog({
  announcement,
  onSaved,
  onClose,
}: {
  announcement?: Announcement;
  onSaved: () => void;
  onClose: () => void;
}) {
  const { user, can } = useCurrentUser();
  const isHr = can("manage_personnel");
  const today = useMemo(() => todayIso(), []);
  const tree = useApiQuery<OrgTreeResponse>("/org/tree/");
  const choices = audienceChoices(tree.data?.nodes ?? [], user?.memberships, isHr);
  const firstLed = user?.memberships?.find((m) => m.is_lead)?.node ?? null;
  const [form, setForm] = useState<AnnouncementForm>(() =>
    announcement ? formFromAnnouncement(announcement) : emptyAnnouncementForm(isHr, firstLed),
  );
  const [touched, setTouched] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const errors = validateAnnouncementForm(form, today, announcement);
  const shown = (key: keyof AnnouncementForm) => (touched ? errors[key] : undefined);
  const set = (patch: Partial<AnnouncementForm>) => setForm((current) => ({ ...current, ...patch }));

  async function submit() {
    setTouched(true);
    if (Object.keys(errors).length > 0) return;
    setSending(true);
    setError(null);
    try {
      if (announcement) {
        const body = announcementPatchPayload(announcement, form);
        if (Object.keys(body).length === 0) {
          onClose();
          return;
        }
        await apiPatch(`/announcements/${announcement.id}/`, body);
      } else {
        await apiPost("/announcements/", announcementPayload(form));
      }
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ذخیره ممکن نشد. دوباره تلاش کنید.");
      setSending(false);
    }
  }

  return (
    <Dialog
      label={announcement ? "ویرایش اطلاعیه" : "انتشار اطلاعیه"}
      title={announcement ? "ویرایش اطلاعیه" : "انتشار اطلاعیه"}
      description={announcement ? "مخاطبان پس از انتشار تغییر نمی‌کنند؛ تغییر متن با برچسب «ویرایش‌شده» نمایش داده می‌شود." : "همهٔ مخاطبان از انتشار باخبر می‌شوند."}
      onClose={onClose}
      busy={sending}
      size="lg"
    >
      <Field label="عنوان" htmlFor="announce-title" required error={shown("title")}>
        <input id="announce-title" value={form.title} maxLength={TITLE_MAX} onChange={(e) => set({ title: e.target.value })} className={inputClass} autoFocus />
      </Field>
      <Field label="متن" htmlFor="announce-body" required error={shown("body")}>
        <textarea id="announce-body" value={form.body} maxLength={BODY_MAX} rows={6} onChange={(e) => set({ body: e.target.value })} className={textareaClass} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        {!announcement && (
          <Field label="مخاطبان" htmlFor="announce-audience" hint="گره و همهٔ زیرمجموعه‌های آن (و مسئولان بالادست).">
            <select
              id="announce-audience"
              value={form.audience_node ?? ""}
              onChange={(e) => set({ audience_node: e.target.value ? Number(e.target.value) : null })}
              className={`${selectClass} w-full`}
              disabled={tree.loading}
            >
              {choices.company && <option value="">همهٔ سازمان</option>}
              {nodeOptions(choices.nodes).map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>
        )}
        <Field label="نمایش تا (اختیاری)" htmlFor="announce-expires" error={shown("expires_on")}>
          <JalaliDatePicker id="announce-expires" value={form.expires_on} onChange={(iso) => set({ expires_on: iso ?? "" })} min={today} />
        </Field>
      </div>
      <label className="flex w-fit items-center gap-2 text-sm text-slate-700">
        <input type="checkbox" className="size-4 rounded" checked={form.pinned} onChange={(e) => set({ pinned: e.target.checked })} />
        سنجاق در بالای فهرست
      </label>
      {error && <ErrorBanner message={error} />}
      <DialogFooter>
        <Button onClick={onClose} disabled={sending}>
          انصراف
        </Button>
        <Button variant="primary" onClick={submit} loading={sending}>
          {announcement ? "ذخیره" : "انتشار"}
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
