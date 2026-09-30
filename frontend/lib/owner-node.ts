/**
 * The node a document belongs to (Phase 14). `GET /documents/owner-nodes/` lists the nodes the
 * caller may pick — those they lead and everything below them (the مدیر عامل: the whole chart), in
 * chart order — and this is the pure logic around that list. Relative imports only.
 */
export interface OwnerNodeChoice {
  id: number;
  name: string;
  kind: "COMPANY" | "DOMAIN" | "UNIT" | "SECTION";
  kind_label: string;
  depth: number;
  /** «حوزه › واحد › بخش», the company's own name left out. */
  label: string;
}

/** What a picker option says: «بخش · IT › هوش مصنوعی › RAG». */
export function ownerNodeText(choice: Pick<OwnerNodeChoice, "kind_label" | "label">): string {
  return `${choice.kind_label} · ${choice.label}`;
}

/**
 * The node a new document starts on: one the person leads (the first, in chart order), else the only
 * choice there is, else nothing — they pick.
 */
export function defaultOwnerNode(
  choices: OwnerNodeChoice[],
  memberships: { node: number; is_lead: boolean }[] | undefined,
): number | null {
  const led = new Set((memberships ?? []).filter((m) => m.is_lead).map((m) => m.node));
  const own = choices.find((choice) => led.has(choice.id));
  if (own) return own.id;
  return choices.length === 1 ? choices[0].id : null;
}
