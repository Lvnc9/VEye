"use client";

import { useApiQuery } from "@/lib/use-api-query";
import type { OrgMembership, Person } from "@/lib/organization";
import type { DraftMember, ProjectRole } from "@/lib/projects";
import type { Paginated } from "@/lib/types";
import { controlClass } from "@/components/ui/Field";
import { Check, Crown, X } from "lucide-react";
import { PersonPicker } from "@/components/PersonPicker";
import { Avatar } from "@/components/ui/Avatar";
import { SkeletonLines } from "@/components/ui/Skeleton";
import { cx } from "@/components/ui/cx";

const select = `${controlClass} h-8 px-2 text-xs`;

/**
 * اعضای پروژه (docs/11 §3.5): seeded from the section's own org members, plus a search for a guest
 * from elsewhere in the company. Purely a client-side draft — nothing is written until the whole
 * project is submitted as one `POST /projects/`, so a half-created project cannot exist.
 */
export function MemberPicker({
  sectionId,
  members,
  onChange,
}: {
  sectionId: number;
  members: DraftMember[];
  onChange: (members: DraftMember[]) => void;
}) {
  const seeded = useApiQuery<Paginated<OrgMembership>>(`/org/nodes/${sectionId}/members/?page_size=200`);
  const memberIds = new Set(members.map((m) => m.user));

  function toggle(user: number, name: string, title: string) {
    if (memberIds.has(user)) {
      onChange(members.filter((m) => m.user !== user));
    } else {
      onChange([...members, { user, name, title, role: "MEMBER" }]);
    }
  }

  function setRole(user: number, role: ProjectRole) {
    onChange(members.map((m) => (m.user === user ? { ...m, role } : m)));
  }

  function addGuest(person: Person) {
    if (memberIds.has(person.id)) return;
    onChange([...members, { user: person.id, name: person.full_name, title: person.title, role: "MEMBER" }]);
  }

  return (
    <div className="space-y-4">
      <div>
        <h4 className="mb-2 text-xs text-slate-500">اعضای بخش</h4>
        {seeded.loading ? (
          <SkeletonLines rows={2} />
        ) : seeded.error ? (
          <p className="text-xs text-rose-600">{seeded.error}</p>
        ) : (seeded.data?.results.length ?? 0) === 0 ? (
          <p className="text-xs text-slate-500">این بخش هنوز عضوی ندارد.</p>
        ) : (
          <ul className="grid gap-2 sm:grid-cols-2">
            {seeded.data!.results.map((membership) => {
              const checked = memberIds.has(membership.user);
              return (
                <li
                  key={membership.user}
                  className={cx(
                    "flex items-center gap-2 rounded-xl border px-3 py-2 text-sm transition-[border-color,background-color] duration-150",
                    checked ? "border-brand-300 bg-brand-50/60" : "border-slate-200 bg-white hover:border-slate-300",
                  )}
                >
                  <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-2.5">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggle(membership.user, membership.user_name, membership.user_title)}
                      className="peer sr-only"
                    />
                    <span className="relative shrink-0 rounded-full peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-brand-500">
                      <Avatar name={membership.user_name} size="sm" />
                      {checked && (
                        <span className="absolute -bottom-0.5 -left-0.5 flex size-3.5 items-center justify-center rounded-full bg-brand-600 text-white ring-2 ring-white animate-pop">
                          <Check className="size-2.5" />
                        </span>
                      )}
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-slate-900">{membership.user_name}</span>
                      <span className="block truncate text-xs text-slate-500">{membership.user_title}</span>
                    </span>
                  </label>
                  {checked && (
                    <select
                      aria-label={`نقش ${membership.user_name}`}
                      value={members.find((m) => m.user === membership.user)?.role}
                      onChange={(e) => setRole(membership.user, e.target.value as ProjectRole)}
                      className={select}
                    >
                      <option value="MEMBER">عضو</option>
                      <option value="MANAGER">مدیر پروژه</option>
                    </select>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <PersonPicker
        id="guest-search"
        label="افزودن از بخش دیگر"
        excludedIds={memberIds}
        onPick={addGuest}
      />

      {members.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs text-slate-500">اعضای انتخاب‌شده ({members.length.toLocaleString("fa-IR")})</h4>
          <ul className="flex flex-wrap gap-2">
            {members.map((member) => (
              <li key={member.user} className="flex items-center gap-1.5 rounded-full bg-white py-1 pe-1 ps-1 text-xs text-slate-700 ring-1 ring-inset ring-slate-200 animate-fade-in">
                <Avatar name={member.name} size="xs" />
                {member.name}
                {member.role === "MANAGER" && (
                  <span className="inline-flex items-center gap-0.5 text-amber-700">
                    <Crown className="size-3" />
                    مدیر
                  </span>
                )}
                <button
                  type="button"
                  aria-label={`حذف ${member.name}`}
                  onClick={() => onChange(members.filter((m) => m.user !== member.user))}
                  className="flex size-5 items-center justify-center rounded-full text-slate-500 transition-colors hover:bg-slate-200 hover:text-slate-800"
                >
                  <X className="size-3.5" />
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
