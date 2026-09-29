"use client";

import { useState } from "react";
import { ApiError, apiDelete, apiPatch, apiPost } from "@/lib/api-client";
import { formatJalali } from "@/lib/jalali";
import { useCurrentUser } from "@/lib/current-user";
import { draftKey, useLocalDraft } from "@/lib/local-draft";
import { meetingBody, splitAcknowledgement, type ProjectMeeting, type ProjectMember } from "@/lib/projects";
import { useApiQuery } from "@/lib/use-api-query";
import { ErrorBanner } from "@/components/StatusBanner";
import { JalaliDatePicker } from "@/components/JalaliDatePicker";
import { buttonClass } from "@/components/ui/Button";
import { controlClass } from "@/components/ui/Field";
import { CalendarDays, Check, Clock, Eye, EyeOff, MapPin, Pencil, Plus, Save, Trash2 } from "lucide-react";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { IconButton } from "@/components/ui/IconButton";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { SkeletonLines } from "@/components/ui/Skeleton";
import { cx } from "@/components/ui/cx";

const input = `${controlClass} w-full px-3 py-2 text-sm`;

/** «جدول جلسات» (docs/12 §D): a real `<table>` from `md` up, stacked cards below that. Only role
 *  MANAGER creates/edits/deletes (`canManageMeetings`, from the project detail); every project reader
 *  sees every meeting; only an invited attendee sees «مشاهده شد». */
export function MeetingsPanel({
  projectId,
  members,
  canManageMeetings,
  onActivity,
}: {
  projectId: number;
  members: ProjectMember[];
  canManageMeetings: boolean;
  /** A meeting was scheduled, changed or cancelled: the page's activity feed should reload. */
  onActivity?: () => void;
}) {
  const [reload, setReload] = useState(0);
  const meetings = useApiQuery<ProjectMeeting[]>(`/projects/${projectId}/meetings/`, reload);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<ProjectMeeting | null>(null);
  const [error, setError] = useState<string | null>(null);

  function refresh() {
    setReload((n) => n + 1);
    onActivity?.();
  }

  const rows = meetings.data ?? [];

  return (
    <Card aria-label="جدول جلسات">
      <CardHeader
        title="جدول جلسات"
        icon={<CalendarDays />}
        actions={
          canManageMeetings &&
          !creating && (
            <Button variant="subtle" size="sm" icon={<Plus />} onClick={() => setCreating(true)}>
              افزودن جلسه
            </Button>
          )
        }
      />
      {error && <ErrorBanner message={error} />}

      {creating && (
        <MeetingForm
          projectId={projectId}
          members={members}
          onSaved={() => {
            setCreating(false);
            refresh();
          }}
          onCancel={() => setCreating(false)}
        />
      )}

      {editing && (
        <MeetingForm
          key={editing.id}
          projectId={projectId}
          members={members}
          meeting={editing}
          onSaved={() => {
            setEditing(null);
            refresh();
          }}
          onCancel={() => setEditing(null)}
        />
      )}

      {meetings.loading ? (
        <SkeletonLines rows={3} />
      ) : meetings.error ? (
        <ErrorBanner message={meetings.error} />
      ) : rows.length === 0 ? (
        <EmptyState compact icon={<CalendarDays />} message="هنوز جلسه‌ای ثبت نشده است." />
      ) : (
        <>
          <div className="-mx-5 hidden overflow-x-auto md:block sm:-mx-6">
          <table className="w-full border-collapse text-start text-sm">
            <thead>
              <tr className="border-y border-slate-100 bg-slate-50/80 text-xs text-slate-500">
                <th className="py-2.5 ps-5 pe-3 font-normal sm:ps-6">تاریخ</th>
                <th className="py-2.5 pe-3 font-normal">ساعت</th>
                <th className="py-2.5 pe-3 font-normal">عنوان</th>
                <th className="py-2.5 pe-3 font-normal">مکان</th>
                <th className="py-2.5 pe-3 font-normal">اعضا</th>
                <th className="py-2.5 pe-5 font-normal sm:pe-6" aria-hidden />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((meeting) => (
                <tr key={meeting.id} className="align-top transition-colors hover:bg-slate-50/60">
                  <td className="py-3 ps-5 pe-3 whitespace-nowrap sm:ps-6">
                    <span className="inline-flex items-center gap-1.5 rounded-lg bg-brand-50 px-2 py-1 text-xs font-bold text-brand-800 ring-1 ring-inset ring-brand-600/15">
                      <CalendarDays className="size-3.5" />
                      {formatJalali(meeting.held_on)}
                    </span>
                  </td>
                  <td className="py-3 pe-3 whitespace-nowrap text-slate-700">
                    {meeting.start_time ? (
                      <span className="inline-flex items-center gap-1 latn">
                        <Clock className="size-3.5 text-slate-400" />
                        {meeting.start_time}
                      </span>
                    ) : (
                      <span className="text-slate-300">—</span>
                    )}
                  </td>
                  <td className="py-3 pe-3">
                    <p className="font-bold text-slate-900">{meeting.title}</p>
                    {meeting.description && <p className="mt-0.5 text-xs leading-6 text-slate-500">{meeting.description}</p>}
                  </td>
                  <td className="py-3 pe-3 text-slate-700">
                    {meeting.location ? (
                      <span className="inline-flex items-center gap-1">
                        <MapPin className="size-3.5 text-slate-400" />
                        {meeting.location}
                      </span>
                    ) : (
                      <span className="text-slate-300">—</span>
                    )}
                  </td>
                  <td className="min-w-48 py-3 pe-3">
                    <AttendeeSummary meeting={meeting} />
                  </td>
                  <td className="py-3 pe-5 sm:pe-6">
                    <MeetingActions projectId={projectId} meeting={meeting} onChanged={refresh} onError={setError} onEdit={() => setEditing(meeting)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>

          <ul className="space-y-3 md:hidden">
            {rows.map((meeting) => (
              <li key={meeting.id} className="rounded-2xl border border-slate-200 p-4">
                <p className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
                  <span className="inline-flex items-center gap-1 rounded-lg bg-brand-50 px-2 py-0.5 font-bold text-brand-800">
                    <CalendarDays className="size-3.5" />
                    {formatJalali(meeting.held_on)}
                  </span>
                  {meeting.start_time && (
                    <span className="inline-flex items-center gap-1 latn">
                      <Clock className="size-3.5" />
                      {meeting.start_time}
                    </span>
                  )}
                  {meeting.location && (
                    <span className="inline-flex items-center gap-1">
                      <MapPin className="size-3.5" />
                      {meeting.location}
                    </span>
                  )}
                </p>
                <p className="mt-2 font-bold text-slate-900">{meeting.title}</p>
                {meeting.description && <p className="mt-0.5 text-sm text-slate-600">{meeting.description}</p>}
                <div className="mt-3">
                  <AttendeeSummary meeting={meeting} />
                </div>
                <div className="mt-3 border-t border-slate-100 pt-3">
                  <MeetingActions projectId={projectId} meeting={meeting} onChanged={refresh} onError={setError} onEdit={() => setEditing(meeting)} />
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  );
}

function AttendeeSummary({ meeting }: { meeting: ProjectMeeting }) {
  const { acknowledged, pending } = splitAcknowledgement(meeting.attendees);
  const ratio = meeting.attendee_count > 0 ? Math.round((meeting.acknowledged_count / meeting.attendee_count) * 100) : 0;
  return (
    <div className="space-y-1.5 text-xs">
      <div className="flex items-center gap-2">
        <ProgressBar value={ratio} tone="bg-emerald-500" className="h-1.5 flex-1" />
        <span className="shrink-0 text-slate-600 tabular-nums">
          {meeting.acknowledged_count} از {meeting.attendee_count} دیده‌اند
        </span>
      </div>
      <p className="flex items-start gap-1 text-slate-600">
        <Eye className="mt-0.5 size-3.5 shrink-0 text-emerald-500" />
        <span>
          <span className="text-slate-500">اعضای متوجه‌شده:</span> {acknowledged.length > 0 ? acknowledged.map((a) => a.name).join("، ") : "—"}
        </span>
      </p>
      <p className="flex items-start gap-1 text-slate-600">
        <EyeOff className="mt-0.5 size-3.5 shrink-0 text-slate-400" />
        <span>
          <span className="text-slate-500">هنوز ندیده‌اند:</span> {pending.length > 0 ? pending.map((a) => a.name).join("، ") : "—"}
        </span>
      </p>
    </div>
  );
}

function MeetingActions({
  projectId,
  meeting,
  onChanged,
  onError,
  onEdit,
}: {
  projectId: number;
  meeting: ProjectMeeting;
  onChanged: () => void;
  onError: (message: string) => void;
  onEdit: () => void;
}) {
  const [busy, setBusy] = useState(false);

  async function acknowledge() {
    setBusy(true);
    try {
      await apiPost(`/projects/${projectId}/meetings/${meeting.id}/acknowledge/`);
      onChanged();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "ثبت مشاهده ممکن نشد.");
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await apiDelete(`/projects/${projectId}/meetings/${meeting.id}/`);
      onChanged();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "حذف جلسه ممکن نشد.");
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center justify-end gap-1 text-xs">
      {meeting.can_acknowledge && meeting.my_acknowledged_at === null && (
        <button type="button" disabled={busy} onClick={acknowledge} className={buttonClass({ variant: "primary", size: "xs" })}>
          <Eye />
          مشاهده شد
        </button>
      )}
      {meeting.can_edit && (
        <>
          <IconButton label="ویرایش" size="sm" onClick={onEdit}>
            <Pencil />
          </IconButton>
          <IconButton label="حذف" tone="danger" size="sm" disabled={busy} onClick={remove}>
            <Trash2 />
          </IconButton>
        </>
      )}
    </div>
  );
}

function MeetingForm({
  projectId,
  members,
  meeting,
  onSaved,
  onCancel,
}: {
  projectId: number;
  members: ProjectMember[];
  /** Present only when editing — its id decides POST vs PATCH and pre-fills the fields. */
  meeting?: ProjectMeeting;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const { user } = useCurrentUser();
  const isEdit = Boolean(meeting);
  const [title, setTitle] = useState(meeting?.title ?? "");
  const [heldOn, setHeldOn] = useState(meeting?.held_on ?? "");
  const [startTime, setStartTime] = useState(meeting?.start_time ?? "");
  const [location, setLocation] = useState(meeting?.location ?? "");
  // The create form's description survives a lost tab; an edit session is scoped to one meeting at a
  // time and isn't — the key schema has no slot for a meeting id to keep several apart. Both hooks
  // run unconditionally (Rules of Hooks); which one backs `description` is picked below, in plain
  // control flow, not by conditionally calling a hook.
  const [meetingDescription, setMeetingDescription] = useState(meeting?.description ?? "");
  const [draftDescription, setDraftDescription, clearDraftDescription] = useLocalDraft(
    !isEdit && user ? draftKey(user.id, projectId, "meeting") : null,
  );
  const description = isEdit ? meetingDescription : draftDescription;
  const setDescription = isEdit ? setMeetingDescription : setDraftDescription;
  // User ids, per the API contract (the same as an objective's assignees) — not ProjectMember ids.
  const [attendees, setAttendees] = useState<number[]>(meeting?.attendees.map((a) => a.user) ?? []);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function toggle(userId: number) {
    setAttendees((current) => (current.includes(userId) ? current.filter((id) => id !== userId) : [...current, userId]));
  }

  async function submit() {
    if (!title.trim() || !heldOn || attendees.length === 0) {
      setError("عنوان، تاریخ و دست‌کم یک عضو الزامی است.");
      return;
    }
    setSaving(true);
    setError(null);
    const body = meetingBody({ title, held_on: heldOn, start_time: startTime, location, description, attendees });
    try {
      if (meeting) {
        await apiPatch(`/projects/${projectId}/meetings/${meeting.id}/`, body);
      } else {
        await apiPost(`/projects/${projectId}/meetings/`, body);
        clearDraftDescription();
      }
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ذخیرهٔ جلسه ممکن نشد.");
      setSaving(false);
    }
  }

  return (
    <div className="mb-5 space-y-4 rounded-2xl border border-dashed border-brand-200 bg-brand-50/30 p-4 animate-fade-in">
      {error && <ErrorBanner message={error} />}
      {isEdit && (
        <p className="rounded-xl border border-amber-200 bg-amber-50/80 px-3 py-2 text-xs text-amber-800">
          تغییر تاریخ، ساعت یا مکان، همهٔ «مشاهده شد»های ثبت‌شده را پاک می‌کند.
        </p>
      )}
      <div>
        <label className="mb-1.5 block text-xs text-slate-600" htmlFor="meeting-title">
          عنوان
        </label>
        <input id="meeting-title" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={255} className={input} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1.5 block text-xs text-slate-600" htmlFor="meeting-date">
            تاریخ
          </label>
          <JalaliDatePicker id="meeting-date" value={heldOn} onChange={(iso) => setHeldOn(iso ?? "")} required />
        </div>
        <div>
          <label className="mb-1.5 block text-xs text-slate-600" htmlFor="meeting-time">
            ساعت (اختیاری)
          </label>
          <input
            id="meeting-time"
            type="time"
            value={startTime}
            onChange={(e) => setStartTime(e.target.value)}
            className={input}
          />
        </div>
      </div>
      <div>
        <label className="mb-1.5 block text-xs text-slate-600" htmlFor="meeting-location">
          مکان (اختیاری)
        </label>
        <input id="meeting-location" value={location} onChange={(e) => setLocation(e.target.value)} maxLength={255} className={input} />
      </div>
      <div>
        <label className="mb-1.5 block text-xs text-slate-600" htmlFor="meeting-description">
          توضیحات (اختیاری)
        </label>
        <textarea id="meeting-description" value={description} onChange={(e) => setDescription(e.target.value)} rows={2} className={input} />
      </div>
      <div>
        <span className="mb-1.5 block text-xs text-slate-600">اعضای دعوت‌شده</span>
        {members.length === 0 ? (
          <p className="text-xs text-slate-500">این پروژه هنوز عضوی ندارد.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {members.map((member) => {
              const on = attendees.includes(member.user);
              return (
                <button
                  key={member.id}
                  type="button"
                  aria-pressed={on}
                  title={member.user_title}
                  onClick={() => toggle(member.user)}
                  className={cx(
                    "flex items-center gap-2 rounded-full py-1 ps-1 pe-3 text-xs ring-1 ring-inset transition-[background-color,box-shadow] duration-150 active:scale-[0.97]",
                    on ? "bg-brand-700 text-white ring-brand-700" : "bg-white text-slate-700 ring-slate-200 hover:ring-slate-300",
                  )}
                >
                  {on ? (
                    <span className="flex size-6 items-center justify-center rounded-full bg-white/20">
                      <Check className="size-3.5" />
                    </span>
                  ) : (
                    <Avatar name={member.user_name} size="xs" />
                  )}
                  {member.user_name}
                </button>
              );
            })}
          </div>
        )}
      </div>
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancel} disabled={saving} className={buttonClass({ variant: "secondary", size: "sm" })}>
          انصراف
        </button>
        <button type="button" onClick={submit} disabled={saving} className={buttonClass({ variant: "primary", size: "sm" })}>
          <Save />
          {saving ? "در حال ذخیره..." : "ذخیره"}
        </button>
      </div>
    </div>
  );
}
