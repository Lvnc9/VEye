"use client";

import { useState } from "react";
import { ApiError, apiDelete, apiPatch, apiPost } from "@/lib/api-client";
import type { ProjectMember, ProjectRole } from "@/lib/projects";
import type { Person } from "@/lib/organization";
import { ErrorBanner } from "@/components/StatusBanner";
import { PersonPicker } from "@/components/PersonPicker";
import { Avatar } from "@/components/ui/Avatar";
import { controlClass } from "@/components/ui/Field";
import { Crown, UserMinus, Users } from "lucide-react";
import { Card, CardHeader } from "@/components/ui/Card";
import { IconButton } from "@/components/ui/IconButton";

const select = `${controlClass} h-8 px-2 text-xs`;

/**
 * اعضای پروژه (Phase 16): add/remove/role-change on the detail page, through the endpoints Phase
 * 8.5/8.6 already wired up for `/projects/new`'s MemberPicker (`POST/PATCH/DELETE
 * /projects/{id}/members/...`) — this is only the UI the detail page was missing
 * (docs/07-known-gaps.md #18). `canEdit` is the same flag that gates the status select and
 * archive button above: the server checks the identical rule either way.
 */
export function MembersPanel({
  projectId,
  members,
  canEdit,
  onChanged,
}: {
  projectId: number;
  members: ProjectMember[];
  canEdit: boolean;
  onChanged: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const memberIds = new Set(members.map((m) => m.user));

  async function setRole(member: ProjectMember, role: ProjectRole) {
    if (role === member.role) return;
    setError(null);
    setBusyId(member.id);
    try {
      await apiPatch(`/projects/${projectId}/members/${member.id}/`, { role });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تغییر نقش ممکن نشد.");
    } finally {
      setBusyId(null);
    }
  }

  async function remove(member: ProjectMember) {
    setError(null);
    setBusyId(member.id);
    try {
      await apiDelete(`/projects/${projectId}/members/${member.id}/`);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "حذف عضو ممکن نشد.");
    } finally {
      setBusyId(null);
    }
  }

  async function add(person: Person) {
    setError(null);
    try {
      await apiPost(`/projects/${projectId}/members/`, { user: person.id });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "افزودن عضو ممکن نشد.");
    }
  }

  return (
    <Card aria-label="اعضای پروژه">
      <CardHeader title="اعضای پروژه" icon={<Users />} />
      {error && <ErrorBanner message={error} />}

      <ul className="flex flex-wrap gap-2">
        {members.map((member) => (
          <li
            key={member.id}
            className="flex items-center gap-1.5 rounded-full bg-white py-1 pe-1 ps-1 text-xs text-slate-700 ring-1 ring-inset ring-slate-200"
          >
            <Avatar name={member.user_name} size="xs" />
            <span>
              {member.user_name}
              {member.is_guest && <span className="text-slate-500"> · مهمان</span>}
            </span>
            {canEdit ? (
              <>
                <select
                  aria-label={`نقش ${member.user_name}`}
                  value={member.role}
                  disabled={busyId === member.id}
                  onChange={(e) => setRole(member, e.target.value as ProjectRole)}
                  className={select}
                >
                  <option value="MEMBER">عضو</option>
                  <option value="MANAGER">مدیر پروژه</option>
                </select>
                <IconButton
                  label={`حذف ${member.user_name}`}
                  tone="danger"
                  size="sm"
                  disabled={busyId === member.id}
                  onClick={() => remove(member)}
                >
                  <UserMinus />
                </IconButton>
              </>
            ) : (
              member.role === "MANAGER" && (
                <span className="inline-flex items-center gap-0.5 text-amber-700">
                  <Crown className="size-3" /> مدیر
                </span>
              )
            )}
          </li>
        ))}
      </ul>

      {canEdit && (
        <div className="mt-4 border-t border-slate-100 pt-4">
          <PersonPicker id="add-member-search" label="افزودن عضو" excludedIds={memberIds} onPick={add} />
        </div>
      )}
    </Card>
  );
}
