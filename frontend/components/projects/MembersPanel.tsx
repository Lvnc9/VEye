"use client";

import { useState } from "react";
import { ApiError, apiDelete, apiPatch, apiPost } from "@/lib/api-client";
import type { ProjectMember, ProjectRole } from "@/lib/projects";
import type { Paginated } from "@/lib/types";
import type { Person } from "@/lib/organization";
import { useApiQuery } from "@/lib/use-api-query";
import { ErrorBanner } from "@/components/StatusBanner";
import { Avatar } from "@/components/ui/Avatar";
import { buttonClass } from "@/components/ui/Button";
import { controlClass } from "@/components/ui/Field";
import { Check, Crown, Search, UserMinus, UserPlus, Users } from "lucide-react";
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
  const [query, setQuery] = useState("");
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
      setQuery("");
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
          <label htmlFor="add-member-search" className="mb-1.5 block text-xs text-slate-500">
            افزودن عضو
          </label>
          <div className="relative">
            <Search className="pointer-events-none absolute inset-y-0 right-3 my-auto size-4 text-slate-400" />
            <input
              id="add-member-search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="جست و جوی نام (دست‌کم دو حرف)"
              className={`${controlClass} h-10 w-full pr-9 pl-3 text-sm`}
            />
          </div>
          {query.trim().length >= 2 && <PersonResults key={query} query={query} memberIds={memberIds} onAdd={add} />}
        </div>
      )}
    </Card>
  );
}

function PersonResults({
  query,
  memberIds,
  onAdd,
}: {
  query: string;
  memberIds: Set<number>;
  onAdd: (person: Person) => void;
}) {
  const people = useApiQuery<Paginated<Person>>(`/org/people/?q=${encodeURIComponent(query)}&page_size=8`);
  if (people.loading) return <p className="mt-2 text-xs text-slate-500">در حال جستجو...</p>;
  if (people.error) return <p className="mt-1 text-xs text-rose-600">{people.error}</p>;
  const rows = people.data?.results ?? [];
  if (rows.length === 0) return <p className="mt-1 text-xs text-slate-500">کسی با این نام پیدا نشد.</p>;
  return (
    <ul className="mt-2 space-y-1.5 animate-fade-in">
      {rows.map((person) => {
        const already = memberIds.has(person.id);
        return (
          <li
            key={person.id}
            className="flex items-center justify-between gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm transition-colors hover:border-slate-300"
          >
            <span className="flex min-w-0 items-center gap-2">
              <Avatar name={person.full_name} size="sm" />
              <span className="min-w-0 truncate">
                {person.full_name} <span className="text-xs text-slate-500">{person.title}</span>
              </span>
            </span>
            <button
              type="button"
              disabled={already}
              onClick={() => onAdd(person)}
              className={buttonClass({ variant: "secondary", size: "xs", className: "shrink-0" })}
            >
              {already ? <Check /> : <UserPlus />}
              {already ? "افزوده شد" : "افزودن"}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
