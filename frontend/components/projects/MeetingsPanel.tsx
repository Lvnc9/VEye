"use client";

import { useState } from "react";
import { ApiError, apiDelete, apiPatch, apiPost } from "@/lib/api-client";
import { formatJalali } from "@/lib/jalali";
import { useCurrentUser } from "@/lib/current-user";
import { draftKey, useLocalDraft } from "@/lib/local-draft";
import { meetingBody, splitAcknowledgement, type ProjectMeeting, type ProjectMember } from "@/lib/projects";
import { useApiQuery } from "@/lib/use-api-query";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
import { JalaliDatePicker } from "@/components/JalaliDatePicker";
import { buttonClass } from "@/components/ui/Button";
import { controlClass } from "@/components/ui/Field";

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
    <section aria-label="جدول جلسات" className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card sm:p-6">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-base font-bold text-slate-900">جدول جلسات</h2>
        {canManageMeetings && !creating && (
          <button type="button" onClick={() => setCreating(true)} className="text-sm text-brand-700 underline-offset-4 transition-colors hover:text-brand-800 hover:underline">
            افزودن جلسه
          </button>
        )}
      </div>
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
        <LoadingBanner />
      ) : meetings.error ? (
        <ErrorBanner message={meetings.error} />
      ) : rows.length === 0 ? (
        <p className="text-sm text-slate-500">هنوز جلسه‌ای ثبت نشده است.</p>
      ) : (
        <>
          <table className="hidden w-full border-collapse text-start text-sm md:table">
            <thead>
              <tr className="border-b border-slate-200 text-xs text-slate-500">
                <th className="py-2 pe-3 font-medium">تاریخ</th>
                <th className="py-2 pe-3 font-medium">ساعت</th>
                <th className="py-2 pe-3 font-medium">عنوان</th>
                <th className="py-2 pe-3 font-medium">مکان</th>
                <th className="py-2 pe-3 font-medium">اعضا</th>
                <th className="py-2 font-medium" aria-hidden />
              </tr>
            </thead>
            <tbody>
              {rows.map((meeting) => (
                <tr key={meeting.id} className="border-b border-slate-100 align-top">
                  <td className="py-2 pe-3 whitespace-nowrap">{formatJalali(meeting.held_on)}</td>
                  <td className="py-2 pe-3 whitespace-nowrap">{meeting.start_time ?? "—"}</td>
                  <td className="py-2 pe-3">
                    <p className="font-medium text-slate-900">{meeting.title}</p>
                    {meeting.description && <p className="mt-0.5 text-xs text-slate-500">{meeting.description}</p>}
                  </td>
                  <td className="py-2 pe-3">{meeting.location || "—"}</td>
                  <td className="py-2 pe-3">
                    <AttendeeSummary meeting={meeting} />
                  </td>
                  <td className="py-2">
                    <MeetingActions projectId={projectId} meeting={meeting} onChanged={refresh} onError={setError} onEdit={() => setEditing(meeting)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <ul className="space-y-3 md:hidden">
            {rows.map((meeting) => (
              <li key={meeting.id} className="rounded-lg border border-slate-100 p-3">
                <p className="text-xs text-slate-500">
                  {formatJalali(meeting.held_on)}
                  {meeting.start_time && <> · {meeting.start_time}</>}
                  {meeting.location && <> · {meeting.location}</>}
                </p>
                <p className="mt-1 font-medium text-slate-900">{meeting.title}</p>
                {meeting.description && <p className="mt-0.5 text-sm text-slate-600">{meeting.description}</p>}
                <div className="mt-2">
                  <AttendeeSummary meeting={meeting} />
                </div>
                <div className="mt-2">
                  <MeetingActions projectId={projectId} meeting={meeting} onChanged={refresh} onError={setError} onEdit={() => setEditing(meeting)} />
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

function AttendeeSummary({ meeting }: { meeting: ProjectMeeting }) {
  const { acknowledged, pending } = splitAcknowledgement(meeting.attendees);
  return (
    <div className="space-y-1 text-xs">
      <p className="text-slate-600">
        {meeting.acknowledged_count} از {meeting.attendee_count} دیده‌اند
      </p>
      <p className="text-slate-500">
        <span className="font-medium">اعضای متوجه‌شده:</span> {acknowledged.length > 0 ? acknowledged.map((a) => a.name).join("، ") : "—"}
      </p>
      <p className="text-slate-500">
        <span className="font-medium">هنوز ندیده‌اند:</span> {pending.length > 0 ? pending.map((a) => a.name).join("، ") : "—"}
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
    <div className="flex flex-wrap items-center gap-2 text-xs">
      {meeting.can_acknowledge && meeting.my_acknowledged_at === null && (
        <button type="button" disabled={busy} onClick={acknowledge} className={buttonClass({ variant: "primary", size: "xs" })}>
          مشاهده شد
        </button>
      )}
      {meeting.can_edit && (
        <>
          <button type="button" onClick={onEdit} className="text-slate-600 underline hover:text-slate-900">
            ویرایش
          </button>
          <button type="button" disabled={busy} onClick={remove} className="text-rose-600 underline hover:text-rose-800 disabled:opacity-50">
            حذف
          </button>
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
    <div className="mb-4 space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
      {error && <ErrorBanner message={error} />}
      {isEdit && (
        <p className="rounded-xl border border-amber-200 bg-amber-50/80 px-3 py-2 text-xs text-amber-800">
          تغییر تاریخ، ساعت یا مکان، همهٔ «مشاهده شد»های ثبت‌شده را پاک می‌کند.
        </p>
      )}
      <div>
        <label className="mb-1 block text-xs text-slate-600" htmlFor="meeting-title">
          عنوان
        </label>
        <input id="meeting-title" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={255} className={input} />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="mb-1 block text-xs text-slate-600" htmlFor="meeting-date">
            تاریخ
          </label>
          <JalaliDatePicker id="meeting-date" value={heldOn} onChange={(iso) => setHeldOn(iso ?? "")} required />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-600" htmlFor="meeting-time">
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
        <label className="mb-1 block text-xs text-slate-600" htmlFor="meeting-location">
          مکان (اختیاری)
        </label>
        <input id="meeting-location" value={location} onChange={(e) => setLocation(e.target.value)} maxLength={255} className={input} />
      </div>
      <div>
        <label className="mb-1 block text-xs text-slate-600" htmlFor="meeting-description">
          توضیحات (اختیاری)
        </label>
        <textarea id="meeting-description" value={description} onChange={(e) => setDescription(e.target.value)} rows={2} className={input} />
      </div>
      <div>
        <span className="mb-1 block text-xs text-slate-600">اعضای دعوت‌شده</span>
        {members.length === 0 ? (
          <p className="text-xs text-slate-500">این پروژه هنوز عضوی ندارد.</p>
        ) : (
          <ul className="max-h-32 space-y-1 overflow-y-auto rounded-xl border border-slate-200 bg-white p-2">
            {members.map((member) => (
              <li key={member.id}>
                <label className="flex items-center gap-2 rounded-lg px-2 py-1 text-sm transition-colors hover:bg-slate-50">
                  <input type="checkbox" checked={attendees.includes(member.user)} onChange={() => toggle(member.user)} />
                  <span className="truncate">{member.user_name}</span>
                  <span className="truncate text-xs text-slate-500">{member.user_title}</span>
                </label>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancel} disabled={saving} className={buttonClass({ variant: "secondary", size: "sm" })}>
          انصراف
        </button>
        <button type="button" onClick={submit} disabled={saving} className={buttonClass({ variant: "primary", size: "sm" })}>
          {saving ? "در حال ذخیره..." : "ذخیره"}
        </button>
      </div>
    </div>
  );
}
