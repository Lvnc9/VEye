"use client";

import { useState } from "react";
import { PersonnelForm } from "@/components/personnel/PersonnelForm";
import { finishBlockedReason } from "@/lib/setup";
import type { Person } from "@/lib/organization";
import type { SetupStatus } from "@/lib/types";
import { useApiQuery } from "@/lib/use-api-query";
import { StepCard, ghostButton, primaryButton } from "./ui";

interface PeoplePage {
  count: number;
  results: Person[];
}

/** Step 4: پرسنل. Register people and place them in the chart in one request (A4's PersonnelForm).
 *  The مدیر عامل goes first: «پایان راه‌اندازی» waits for an active lead on «خود شرکت». Everyone
 *  else can be added now or later from «ثبت پرسنل». */
export function PeopleStep({
  status,
  onRegistered,
  onBack,
  onNext,
}: {
  status: SetupStatus;
  /** Someone was registered: the wizard refetches the status (has_root_lead) and the chart. */
  onRegistered: () => void;
  onBack: () => void;
  onNext: () => void;
}) {
  const [reload, setReload] = useState(0);
  const people = useApiQuery<PeoplePage>("/org/people/", reload);
  const blocked = finishBlockedReason(status);
  const list = people.data?.results ?? [];

  return (
    <StepCard
      title="پرسنل"
      intro="افراد را ثبت کنید و همان‌جا جایگاهشان را در ساختار سازمان انتخاب کنید. ابتدا مدیر عامل را در «خود شرکت» با گزینهٔ «مسئول» ثبت کنید؛ بقیه را می‌توانید اکنون یا بعداً از «ثبت پرسنل» بیفزایید."
    >
      <p
        role="status"
        className={`rounded-lg border px-3.5 py-2.5 text-sm ${
          blocked
            ? "border-amber-500/40 bg-amber-500/10 text-amber-200"
            : "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
        }`}
      >
        {blocked ?? "مسئول شرکت ثبت شده است؛ می‌توانید راه‌اندازی را به پایان برسانید."}
      </p>

      <div className="rounded-xl border border-line p-4">
        <PersonnelForm
          tone="dark"
          onRegistered={() => {
            setReload((n) => n + 1);
            onRegistered();
          }}
        />
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold text-slate-200">
          ثبت‌شده‌ها{people.data ? ` (${people.data.count})` : ""}
        </h3>
        {people.error ? (
          <p className="text-xs text-rose-300">{people.error}</p>
        ) : list.length === 0 ? (
          <p className="text-xs text-slate-500">هنوز کسی ثبت نشده است.</p>
        ) : (
          <ul className="max-h-64 space-y-1 overflow-y-auto">
            {list.map((person) => (
              <li key={person.id} className="rounded-lg bg-white/5 px-3 py-2 text-sm text-slate-200">
                <span className="font-medium">{person.full_name}</span>
                <span className="text-xs text-slate-400">
                  {person.memberships.length === 0
                    ? " — هنوز جایگاهی ندارد"
                    : ` — ${person.memberships
                        .map((m) => `${m.is_lead ? "مسئول " : ""}${m.node_name}${m.position_label ? ` (${m.position_label})` : ""}`)
                        .join("، ")}`}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="flex justify-between">
        <button type="button" onClick={onBack} className={ghostButton}>
          بازگشت
        </button>
        <button type="button" onClick={onNext} className={primaryButton}>
          ادامه: آمادهٔ شروع
        </button>
      </div>
    </StepCard>
  );
}
