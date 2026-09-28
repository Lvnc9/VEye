import Link from "next/link";
import { AlarmClock, ChevronLeft } from "lucide-react";
import { AvatarStack } from "@/components/ui/Avatar";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { PROJECT_STATUS_TONE, progressBarTone, progressLabel, type Project } from "@/lib/projects";

/** One row of «پروژه‌ها»: status, weighted progress, member avatars, overdue count (docs/11 §3.5). */
export function ProjectCard({ project }: { project: Project }) {
  return (
    <Link
      href={`/projects/${project.id}`}
      className="group flex flex-col rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card transition-[box-shadow,transform,border-color] duration-200 hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-raised"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-base font-bold text-slate-900 transition-colors group-hover:text-brand-800">
            {project.name}
          </h3>
          <p className="mt-0.5 truncate text-xs text-slate-500">{project.section_name}</p>
        </div>
        <span
          className={`shrink-0 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs ${PROJECT_STATUS_TONE[project.status]}`}
        >
          {project.status_label}
        </span>
      </div>

      <div className="mt-4 flex items-center gap-3">
        <ProgressBar value={project.progress} tone={progressBarTone(project.progress)} className="flex-1" />
        <span className="shrink-0 text-xs font-bold text-slate-600 tabular-nums">{progressLabel(project.progress)}</span>
      </div>

      <div className="mt-4 flex items-center justify-between gap-2 border-t border-slate-100 pt-3">
        <AvatarStack
          names={project.members_preview.map((member) => member.name)}
          total={project.member_count}
          label={`${project.member_count} عضو`}
        />
        <span className="flex items-center gap-2">
          {project.overdue_count > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-xs text-rose-800 ring-1 ring-inset ring-rose-600/20">
              <AlarmClock className="size-3.5" />
              {project.overdue_count} ریزهدف دیرکرد
            </span>
          )}
          <ChevronLeft className="size-4 text-slate-300 transition-transform duration-200 group-hover:-translate-x-0.5 group-hover:text-slate-500" />
        </span>
      </div>
    </Link>
  );
}
