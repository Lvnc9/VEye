"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { ApiError, apiPatch, apiPost } from "@/lib/api-client";
import { formatJalali } from "@/lib/jalali";
import { initials } from "@/lib/organization";
import {
  PROJECT_STATUS_LABELS,
  PROJECT_STATUS_TONE,
  progressBarTone,
  progressLabel,
  type Objective,
  type ProjectDetail,
  type ProjectStatus,
} from "@/lib/projects";
import { useApiQuery } from "@/lib/use-api-query";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
import { CommentsPanel } from "@/components/projects/CommentsPanel";
import { DocumentLinksPanel } from "@/components/projects/DocumentLinksPanel";
import { ObjectivesList } from "@/components/projects/ObjectivesList";
import { ProjectActivityFeed } from "@/components/projects/ProjectActivityFeed";

const select = "rounded border border-slate-300 bg-white px-2 py-1.5 text-sm";

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const [reload, setReload] = useState(0);
  const project = useApiQuery<ProjectDetail>(`/projects/${projectId}/`, reload);
  const objectives = useApiQuery<Objective[]>(`/projects/${projectId}/objectives/`, reload);
  const [error, setError] = useState<string | null>(null);
  const [archiving, setArchiving] = useState(false);

  function refresh() {
    setReload((n) => n + 1);
  }

  async function changeStatus(status: ProjectStatus) {
    setError(null);
    try {
      await apiPatch(`/projects/${projectId}/`, { status });
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تغییر وضعیت ممکن نشد.");
    }
  }

  async function toggleArchive() {
    if (!project.data) return;
    setArchiving(true);
    setError(null);
    try {
      await apiPost(`/projects/${projectId}/${project.data.is_archived ? "unarchive" : "archive"}/`);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تغییر بایگانی ممکن نشد.");
    } finally {
      setArchiving(false);
    }
  }

  if (project.loading) return <LoadingBanner />;
  if (project.error || !project.data) return <ErrorBanner message={project.error ?? "دریافت پروژه ممکن نشد."} />;
  const data = project.data;

  return (
    <div className="space-y-6">
      {error && <ErrorBanner message={error} />}

      <header className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-2xl font-bold text-slate-900">{data.name}</h1>
            <p className="mt-1 text-sm text-slate-500">{data.section_name}</p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {data.can_edit ? (
              <select
                aria-label="وضعیت پروژه"
                value={data.status}
                onChange={(e) => changeStatus(e.target.value as ProjectStatus)}
                className={`${select} ${PROJECT_STATUS_TONE[data.status]}`}
              >
                {(Object.keys(PROJECT_STATUS_LABELS) as ProjectStatus[]).map((value) => (
                  <option key={value} value={value}>
                    {PROJECT_STATUS_LABELS[value]}
                  </option>
                ))}
              </select>
            ) : (
              <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${PROJECT_STATUS_TONE[data.status]}`}>
                {data.status_label}
              </span>
            )}
            {data.can_edit && (
              <button
                type="button"
                disabled={archiving}
                onClick={toggleArchive}
                className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                {data.is_archived ? "خروج از بایگانی" : "بایگانی"}
              </button>
            )}
          </div>
        </div>

        {data.is_archived && (
          <p className="mt-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            این پروژه بایگانی شده و فقط‌خواندنی است.
          </p>
        )}

        {data.goal && <p className="mt-3 text-sm leading-7 text-slate-700">{data.goal}</p>}

        <div className="mt-4 flex items-center gap-2">
          <div className="h-2.5 max-w-sm flex-1 overflow-hidden rounded-full bg-slate-100" role="presentation">
            <div className={`h-full rounded-full ${progressBarTone(data.progress)}`} style={{ width: `${data.progress ?? 0}%` }} />
          </div>
          <span className="text-sm text-slate-600">{progressLabel(data.progress)}</span>
          {data.overdue_count > 0 && (
            <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800">
              {data.overdue_count} ریزهدف دیرکرد
            </span>
          )}
        </div>

        <dl className="mt-4 grid grid-cols-2 gap-3 text-xs text-slate-500 sm:grid-cols-4">
          <div>
            <dt>تاریخ شروع</dt>
            <dd className="text-slate-800">{data.starts_on ? formatJalali(data.starts_on) : "—"}</dd>
          </div>
          <div>
            <dt>مهلت پروژه</dt>
            <dd className="text-slate-800">{data.due_on ? formatJalali(data.due_on) : "—"}</dd>
          </div>
          <div>
            <dt>تاریخ ایجاد</dt>
            <dd className="text-slate-800">{formatJalali(data.created_at)}</dd>
          </div>
          <div>
            <dt>تعداد اعضا</dt>
            <dd className="text-slate-800">{data.member_count}</dd>
          </div>
        </dl>

        <div className="mt-4 flex flex-wrap gap-2 border-t border-slate-100 pt-4">
          {data.members.map((member) => (
            <span
              key={member.id}
              title={`${member.user_name} — ${member.role_label}`}
              className="flex items-center gap-1.5 rounded-full bg-slate-100 py-1 pe-3 ps-1 text-xs text-slate-700"
            >
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-700 text-[10px] font-bold text-white">
                {initials(member.user_name)}
              </span>
              {member.user_name}
              {member.role === "MANAGER" && <span className="text-slate-500">(مدیر)</span>}
              {member.is_guest && <span className="text-slate-400">· مهمان</span>}
            </span>
          ))}
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-6">
          {objectives.loading ? (
            <LoadingBanner />
          ) : objectives.error ? (
            <ErrorBanner message={objectives.error} />
          ) : (
            <ObjectivesList project={data} objectives={objectives.data ?? []} onChanged={refresh} />
          )}
          <CommentsPanel projectId={projectId} />
          <DocumentLinksPanel projectId={projectId} canEdit={data.can_edit} />
        </div>
        <aside>
          <ProjectActivityFeed projectId={projectId} version={reload} />
        </aside>
      </div>
    </div>
  );
}
