"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { ApiError, apiPatch, apiPost } from "@/lib/api-client";
import { formatJalali } from "@/lib/jalali";
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
import { MeetingsPanel } from "@/components/projects/MeetingsPanel";
import { MembersPanel } from "@/components/projects/MembersPanel";
import { ObjectiveTree } from "@/components/projects/ObjectiveTree";
import { ProjectActivityFeed } from "@/components/projects/ProjectActivityFeed";
import { AlarmClock, Archive, ArchiveRestore, ArrowRight, CalendarClock, CalendarPlus, Flag, Users } from "lucide-react";
import Link from "next/link";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { cardClass } from "@/components/ui/Card";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { cx } from "@/components/ui/cx";

// A status select is tinted with its status's own tone rather than the white control look.
const select = "h-9 rounded-lg border-0 px-2.5 text-sm transition-shadow focus:outline-none focus:ring-4 focus:ring-brand-500/15";

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

  const facts: { label: string; value: string | number; icon: React.ReactNode }[] = [
    { label: "تاریخ شروع", value: data.starts_on ? formatJalali(data.starts_on) : "—", icon: <Flag /> },
    { label: "مهلت پروژه", value: data.due_on ? formatJalali(data.due_on) : "—", icon: <CalendarClock /> },
    { label: "تاریخ ایجاد", value: formatJalali(data.created_at), icon: <CalendarPlus /> },
    { label: "تعداد اعضا", value: data.member_count, icon: <Users /> },
  ];

  return (
    <div className="space-y-6">
      <nav className="text-sm">
        <Link
          href="/projects"
          className="group inline-flex items-center gap-1.5 text-slate-500 transition-colors hover:text-slate-900"
        >
          <ArrowRight className="size-4 transition-transform duration-200 group-hover:translate-x-0.5" />
          پروژه‌ها
        </Link>
      </nav>

      {error && <ErrorBanner message={error} />}

      <header className={cx(cardClass, "relative overflow-hidden p-5 sm:p-6")}>
        <div aria-hidden className="absolute inset-x-0 top-0 h-1 bg-gradient-to-l from-brand-500 via-indigo-400 to-emerald-400 opacity-80" />
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-2xl font-bold leading-10 text-slate-900">{data.name}</h1>
            <p className="mt-0.5 text-sm text-slate-500">{data.section_name}</p>
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
              <span className={`rounded-full px-2.5 py-0.5 text-xs ${PROJECT_STATUS_TONE[data.status]}`}>
                {data.status_label}
              </span>
            )}
            {data.can_edit && (
              <Button
                size="sm"
                loading={archiving}
                onClick={toggleArchive}
                icon={data.is_archived ? <ArchiveRestore /> : <Archive />}
              >
                {data.is_archived ? "خروج از بایگانی" : "بایگانی"}
              </Button>
            )}
          </div>
        </div>

        {data.is_archived && (
          <Alert tone="warning" className="mt-4">
            این پروژه بایگانی شده و فقط‌خواندنی است.
          </Alert>
        )}

        {data.goal && <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-700">{data.goal}</p>}

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <ProgressBar
            value={data.progress}
            tone={progressBarTone(data.progress)}
            className="h-2.5 min-w-40 max-w-md flex-1"
            label="پیشرفت پروژه"
          />
          <span className="text-sm font-bold text-slate-700 tabular-nums">{progressLabel(data.progress)}</span>
          {data.overdue_count > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-xs text-rose-800 ring-1 ring-inset ring-rose-600/20">
              <AlarmClock className="size-3.5" />
              {data.overdue_count} ریزهدف دیرکرد
            </span>
          )}
        </div>

        <dl className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {facts.map((fact) => (
            <div key={fact.label} className="flex items-center gap-3 rounded-xl bg-slate-50 px-3 py-2.5 ring-1 ring-inset ring-slate-200/70">
              <span className="text-slate-400 [&_svg]:size-4">{fact.icon}</span>
              <div className="min-w-0">
                <dt className="text-xs text-slate-500">{fact.label}</dt>
                <dd className="truncate text-sm font-bold text-slate-800 tabular-nums">{fact.value}</dd>
              </div>
            </div>
          ))}
        </dl>
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-6">
          {objectives.loading ? (
            <LoadingBanner />
          ) : objectives.error ? (
            <ErrorBanner message={objectives.error} />
          ) : (
            <ObjectiveTree project={data} objectives={objectives.data ?? []} onChanged={refresh} />
          )}
          <MembersPanel projectId={projectId} members={data.members} canEdit={data.can_edit} onChanged={refresh} />
          <MeetingsPanel
            projectId={projectId}
            members={data.members}
            canManageMeetings={data.can_manage_meetings}
            onActivity={refresh}
          />
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
