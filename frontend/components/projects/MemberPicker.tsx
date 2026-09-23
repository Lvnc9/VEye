"use client";

import { useState } from "react";
import { useApiQuery } from "@/lib/use-api-query";
import type { OrgMembership, Person } from "@/lib/organization";
import type { DraftMember, ProjectRole } from "@/lib/projects";
import type { Paginated } from "@/lib/types";

const button = "rounded border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50 disabled:opacity-50";
const select = "rounded border border-slate-300 bg-white px-2 py-1 text-xs";

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
  const [guestQuery, setGuestQuery] = useState("");
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
    setGuestQuery("");
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="mb-2 text-sm font-medium text-slate-700">اعضای بخش</h3>
        {seeded.loading ? (
          <p className="text-xs text-slate-500">در حال بارگذاری...</p>
        ) : seeded.error ? (
          <p className="text-xs text-red-600">{seeded.error}</p>
        ) : (seeded.data?.results.length ?? 0) === 0 ? (
          <p className="text-xs text-slate-500">این بخش هنوز عضوی ندارد.</p>
        ) : (
          <ul className="space-y-1">
            {seeded.data!.results.map((membership) => {
              const checked = memberIds.has(membership.user);
              return (
                <li key={membership.user} className="flex items-center gap-2 rounded border border-slate-100 px-3 py-1.5 text-sm">
                  <label className="flex flex-1 items-center gap-2">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggle(membership.user, membership.user_name, membership.user_title)}
                    />
                    <span className="truncate">{membership.user_name}</span>
                    <span className="truncate text-xs text-slate-500">{membership.user_title}</span>
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

      <div>
        <label htmlFor="guest-search" className="mb-1 block text-sm font-medium text-slate-700">
          افزودن از بخش دیگر
        </label>
        <input
          id="guest-search"
          value={guestQuery}
          onChange={(e) => setGuestQuery(e.target.value)}
          placeholder="جست و جوی نام (دست‌کم دو حرف)"
          className="w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm"
        />
        {guestQuery.trim().length >= 2 && (
          <GuestResults key={guestQuery} query={guestQuery} memberIds={memberIds} onAdd={addGuest} />
        )}
      </div>

      {members.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-medium text-slate-700">اعضای انتخاب‌شده ({members.length})</h3>
          <ul className="flex flex-wrap gap-2">
            {members.map((member) => (
              <li key={member.user} className="flex items-center gap-1.5 rounded-full bg-slate-100 py-1 pe-1 ps-3 text-xs text-slate-700">
                {member.name}
                {member.role === "MANAGER" && <span className="text-slate-500">(مدیر)</span>}
                <button
                  type="button"
                  aria-label={`حذف ${member.name}`}
                  onClick={() => onChange(members.filter((m) => m.user !== member.user))}
                  className="rounded-full px-1.5 text-slate-500 hover:bg-slate-200 hover:text-slate-800"
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function GuestResults({ query, memberIds, onAdd }: { query: string; memberIds: Set<number>; onAdd: (person: Person) => void }) {
  const people = useApiQuery<Paginated<Person>>(`/org/people/?q=${encodeURIComponent(query)}&page_size=8`);
  if (people.loading) return <p className="mt-1 text-xs text-slate-500">در حال جستجو...</p>;
  if (people.error) return <p className="mt-1 text-xs text-red-600">{people.error}</p>;
  const rows = people.data?.results ?? [];
  if (rows.length === 0) return <p className="mt-1 text-xs text-slate-500">کسی با این نام پیدا نشد.</p>;
  return (
    <ul className="mt-1 space-y-1">
      {rows.map((person) => {
        const already = memberIds.has(person.id);
        return (
          <li key={person.id} className="flex items-center justify-between gap-2 rounded border border-slate-100 px-3 py-1.5 text-sm">
            <span className="min-w-0 truncate">
              {person.full_name} <span className="text-xs text-slate-500">{person.title}</span>
            </span>
            <button type="button" disabled={already} onClick={() => onAdd(person)} className={button}>
              {already ? "افزوده شد" : "افزودن"}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
