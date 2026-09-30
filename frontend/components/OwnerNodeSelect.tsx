"use client";

import { ownerNodeText, type OwnerNodeChoice } from "@/lib/owner-node";
import { useApiQuery } from "@/lib/use-api-query";
import { selectClass } from "@/components/ui/Field";

/** The nodes the signed-in person may make a document's owner (`GET /documents/owner-nodes/`): those they lead
 *  and everything below them; the مدیر عامل sees the whole chart; someone who leads nothing sees none. */
export function useOwnerNodeChoices(): { choices: OwnerNodeChoice[]; loading: boolean } {
  const query = useApiQuery<OwnerNodeChoice[]>("/documents/owner-nodes/");
  return { choices: query.data ?? [], loading: query.loading };
}

/** A select of those nodes. `value` is a node id or null («انتخاب کنید»). */
export function OwnerNodeSelect({
  value,
  choices,
  disabled,
  onChange,
  id,
  className,
  label = "گرهٔ مالک",
}: {
  value: number | null;
  choices: OwnerNodeChoice[];
  disabled?: boolean;
  onChange: (id: number | null) => void;
  id?: string;
  className?: string;
  label?: string;
}) {
  return (
    <select
      id={id}
      aria-label={label}
      value={value ?? ""}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value === "" ? null : Number(event.target.value))}
      className={`${selectClass} ${className ?? "w-full"}`}
    >
      <option value="">انتخاب کنید</option>
      {choices.map((choice) => (
        <option key={choice.id} value={choice.id}>
          {ownerNodeText(choice)}
        </option>
      ))}
    </select>
  );
}
