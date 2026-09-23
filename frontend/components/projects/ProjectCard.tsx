import Link from "next/link";
import { initials } from "@/lib/organization";
import { PROJECT_STATUS_TONE, progressBarTone, progressLabel, type Project } from "@/lib/projects";

const AVATAR_PREVIEW = 4;

/** One row of «پروژه‌ها»: status, weighted progress, member avatars, overdue count (docs/11 §3.5). */
export function ProjectCard({ project }: { project: Project }) {
  const extra = project.member_count - AVATAR_PREVIEW;
  return (
    <Link
      href={`/projects/${project.id}`}
      className="block rounded-lg border border-slate-200 bg-white p-4 shadow-sm transition-colors hover:border-slate-300 hover:bg-slate-50"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-base font-semibold text-slate-900">{project.name}</h3>
          <p className="mt-0.5 text-xs text-slate-500">{project.section_name}</p>
        </div>
        <span className={`shrink-0 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ${PROJECT_STATUS_TONE[project.status]}`}>
          {project.status_label}
        </span>
      </div>

      <div className="mt-3 flex items-center gap-2">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100" role="presentation">
          <div
            className={`h-full rounded-full ${progressBarTone(project.progress)}`}
            style={{ width: `${project.progress ?? 0}%` }}
          />
        </div>
        <span className="shrink-0 text-xs text-slate-500">{progressLabel(project.progress)}</span>
      </div>

      <div className="mt-3 flex items-center justify-between">
        <div className="flex -space-x-2 space-x-reverse" aria-label={`${project.member_count} عضو`}>
          {project.members_preview.slice(0, AVATAR_PREVIEW).map((member) => (
            <span
              key={member.user}
              title={member.name}
              className="flex h-7 w-7 items-center justify-center rounded-full border-2 border-white bg-slate-700 text-[10px] font-bold text-white"
            >
              {initials(member.name)}
            </span>
          ))}
          {extra > 0 && (
            <span className="flex h-7 w-7 items-center justify-center rounded-full border-2 border-white bg-slate-300 text-[10px] font-bold text-slate-700">
              +{extra}
            </span>
          )}
        </div>
        {project.overdue_count > 0 && (
          <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800">
            {project.overdue_count} ریزهدف دیرکرد
          </span>
        )}
      </div>
    </Link>
  );
}
