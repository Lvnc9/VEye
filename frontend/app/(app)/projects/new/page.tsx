"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ApiError, apiDelete, apiGet, apiPost, apiPut } from "@/lib/api-client";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
import { JalaliDatePicker } from "@/components/JalaliDatePicker";
import { MemberPicker } from "@/components/projects/MemberPicker";
import { formatJalali } from "@/lib/jalali";
import { nodeOptions, type OrgTreeResponse } from "@/lib/organization";
import { useCurrentUser } from "@/lib/current-user";
import {
  EMPTY_CREATE_FORM,
  canAddDraftObjective,
  createProjectBody,
  parseDraftPayload,
  pruneOrphanAssignees,
  serializeDraft,
  validateCreateForm,
  type CreateErrors,
  type DraftMember,
  type DraftObjective,
  type Project,
  type ProjectCreateForm,
} from "@/lib/projects";
import { useApiQuery } from "@/lib/use-api-query";

const input = "w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm";
const label = "mb-1 block text-sm font-medium text-slate-700";
const DRAFT_DEBOUNCE_MS = 1500;

function emptyDraft(): DraftObjective {
  return { key: crypto.randomUUID(), title: "", assignees: [], due_on: "", weight: 1 };
}

/** ایجاد پروژه (docs/11 §3.5, docs/12 §D): one page, four blocks, submitted as one `POST /projects/`
 *  with a nested `objectives` array — a half-created project is impossible. Autosaves a server-side
 *  draft so a half-typed form survives a lost tab. */
export default function NewProjectPage() {
  const router = useRouter();
  const { user } = useCurrentUser();
  const tree = useApiQuery<OrgTreeResponse>("/org/tree/");
  const [form, setForm] = useState<ProjectCreateForm>(EMPTY_CREATE_FORM);
  const [draft, setDraft] = useState<DraftObjective>(emptyDraft());
  const [errors, setErrors] = useState<CreateErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // --- Server-side draft: load once, offer «ادامهٔ پیش‌نویس» / «شروع از نو», then autosave. ---
  const [draftState, setDraftState] = useState<"checking" | "banner" | "ready">("checking");
  const [pendingDraft, setPendingDraft] = useState<ProjectCreateForm | null>(null);
  const formRef = useRef(form);
  const draftReadyRef = useRef(false);
  /** Set while (and after) the create request runs: the server deletes the draft on success, so no
   *  autosave — debounced or the unmount flush — may put it back. Cleared again if the create fails. */
  const submittedRef = useRef(false);
  useEffect(() => {
    formRef.current = form;
    draftReadyRef.current = draftState === "ready";
  }, [form, draftState]);

  useEffect(() => {
    let cancelled = false;
    apiGet<{ payload: unknown; updated_at: string | null }>("/projects/draft/")
      .then((res) => {
        if (cancelled) return;
        const parsed = parseDraftPayload(res.payload);
        if (parsed) {
          setPendingDraft(parsed);
          setDraftState("banner");
        } else {
          setDraftState("ready");
        }
      })
      .catch(() => !cancelled && setDraftState("ready"));
    return () => {
      cancelled = true;
    };
  }, []);

  // Debounced autosave, 1.5s after the last change, while there is nothing left to decide.
  useEffect(() => {
    if (draftState !== "ready") return;
    const timer = setTimeout(() => {
      if (submittedRef.current) return;
      apiPut("/projects/draft/", serializeDraft(form)).catch(() => {});
    }, DRAFT_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [form, draftState]);

  // One last save on unmount, via refs so this effect only ever runs once.
  useEffect(() => {
    return () => {
      if (draftReadyRef.current && !submittedRef.current) {
        apiPut("/projects/draft/", serializeDraft(formRef.current)).catch(() => {});
      }
    };
  }, []);

  function continueDraft() {
    if (pendingDraft) setForm(pendingDraft);
    setDraftState("ready");
  }

  async function discardDraft() {
    setDraftState("ready");
    setForm(EMPTY_CREATE_FORM);
    try {
      await apiDelete("/projects/draft/");
    } catch {
      // نبود پیش‌نویس یا خطای شبکه در حذف پیش‌نویس، مانع شروع از نو نمی‌شود.
    }
  }

  const set = <K extends keyof ProjectCreateForm>(key: K, value: ProjectCreateForm[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  // Bug fix (docs/12 §D): changing the بخش, or removing a member in MemberPicker, used to leave orphan
  // assignees on draft objectives — prune them at the moment the candidate member set changes, rather
  // than reactively (an effect that both reads and writes `form` just to keep it consistent with
  // itself is the wrong tool; the event that changes `members` already knows what to prune).
  function applyMembers(members: DraftMember[]) {
    const memberIds = new Set(members.map((m) => m.user));
    setForm((f) => ({ ...f, members, objectives: pruneOrphanAssignees(f.objectives, memberIds) }));
    setDraft((d) => ({ ...d, assignees: d.assignees.filter((id) => memberIds.has(id)) }));
  }

  // Bug fix (docs/12 §D): the creator was missing from the assignee choices — the backend always adds
  // them as مدیر پروژه regardless of `members`, so the client should offer them too, from the start.
  function selectSection(sectionId: number | null) {
    const creator: DraftMember[] =
      sectionId && user ? [{ user: user.id, name: user.full_name, title: user.title, role: "MANAGER" }] : [];
    set("section", sectionId);
    applyMembers(creator);
  }

  function toggleDraftAssignee(user_: number) {
    setDraft((d) => ({ ...d, assignees: d.assignees.includes(user_) ? d.assignees.filter((u) => u !== user_) : [...d.assignees, user_] }));
  }

  function addObjective() {
    if (!canAddDraftObjective(draft)) return;
    setForm((f) => ({ ...f, objectives: [...f.objectives, draft] }));
    setDraft(emptyDraft());
  }

  function removeObjective(key: string) {
    setForm((f) => ({ ...f, objectives: f.objectives.filter((o) => o.key !== key) }));
  }

  function assigneeNames(assignees: number[]): string {
    return assignees
      .map((id) => form.members.find((m) => m.user === id)?.name)
      .filter((name): name is string => Boolean(name))
      .join("، ");
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const found = validateCreateForm(form);
    setErrors(found);
    setServerError(null);
    if (Object.keys(found).length > 0) return;

    setSaving(true);
    submittedRef.current = true;
    try {
      const project = await apiPost<Project>("/projects/", createProjectBody(form));
      router.push(`/projects/${project.id}`);
    } catch (err) {
      submittedRef.current = false; // the create failed: the server kept the draft, and autosave resumes
      setServerError(err instanceof ApiError ? err.message : "ایجاد پروژه ممکن نشد.");
      setSaving(false);
    }
  }

  if (tree.loading) return <LoadingBanner />;
  if (tree.error || !tree.data) return <ErrorBanner message={tree.error ?? "دریافت ساختار سازمان ممکن نشد."} />;

  const sections = nodeOptions(tree.data.nodes, { kinds: ["SECTION"] });

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">پروژهٔ جدید</h1>

      {draftState === "banner" && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <span>پیش‌نویس ذخیره‌شده دارید.</span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={continueDraft}
              className="rounded bg-amber-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-800"
            >
              ادامهٔ پیش‌نویس
            </button>
            <button
              type="button"
              onClick={discardDraft}
              className="rounded border border-amber-300 bg-white px-3 py-1.5 text-xs text-amber-900 hover:bg-amber-100"
            >
              شروع از نو
            </button>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6 rounded-lg border border-slate-200 bg-white p-6 shadow-sm" noValidate>
        {serverError && <ErrorBanner message={serverError} />}

        <div>
          <label className={label} htmlFor="section">
            بخش
          </label>
          {sections.length === 0 ? (
            <p className="rounded border border-dashed border-slate-300 px-3 py-2 text-xs text-slate-500">
              هنوز بخشی در ساختار سازمان تعریف نشده است.
            </p>
          ) : (
            <select
              id="section"
              value={form.section ?? ""}
              onChange={(e) => selectSection(e.target.value ? Number(e.target.value) : null)}
              className={input}
            >
              <option value="">انتخاب کنید…</option>
              {sections.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          )}
          {errors.section && <p className="mt-1 text-xs text-red-600">{errors.section}</p>}
        </div>

        <div>
          <label className={label} htmlFor="name">
            نام پروژه
          </label>
          <input id="name" value={form.name} onChange={(e) => set("name", e.target.value)} maxLength={255} className={input} />
          {errors.name && <p className="mt-1 text-xs text-red-600">{errors.name}</p>}
        </div>

        {form.section !== null && (
          <div>
            <h2 className={label}>اعضای پروژه</h2>
            <MemberPicker sectionId={form.section} members={form.members} onChange={applyMembers} />
          </div>
        )}

        <div>
          <label className={label} htmlFor="goal">
            هدف پروژه
          </label>
          <textarea id="goal" value={form.goal} onChange={(e) => set("goal", e.target.value)} rows={3} className={input} />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={label} htmlFor="starts_on">
              تاریخ شروع (اختیاری)
            </label>
            <JalaliDatePicker
              id="starts_on"
              value={form.starts_on}
              max={form.due_on || undefined}
              onChange={(iso) => set("starts_on", iso ?? "")}
            />
          </div>
          <div>
            <label className={label} htmlFor="due_on">
              مهلت پروژه (اختیاری)
            </label>
            <JalaliDatePicker
              id="due_on"
              value={form.due_on}
              min={form.starts_on || undefined}
              onChange={(iso) => set("due_on", iso ?? "")}
            />
            {errors.due_on && <p className="mt-1 text-xs text-red-600">{errors.due_on}</p>}
          </div>
        </div>

        <div className="space-y-3 border-t border-slate-100 pt-4">
          <h2 className={label}>برنامه‌ریزی (ریزهدف‌ها)</h2>
          {form.objectives.length > 0 && (
            <ul className="space-y-1">
              {form.objectives.map((objective) => (
                <li key={objective.key} className="flex items-center justify-between gap-2 rounded border border-slate-100 bg-slate-50 px-3 py-1.5 text-sm">
                  <span className="min-w-0 truncate">
                    {objective.title} — {assigneeNames(objective.assignees)} — {formatJalali(objective.due_on)}
                  </span>
                  <button
                    type="button"
                    onClick={() => removeObjective(objective.key)}
                    className="shrink-0 text-xs text-red-600 hover:underline"
                  >
                    حذف
                  </button>
                </li>
              ))}
            </ul>
          )}

          {form.section !== null && form.members.length > 0 ? (
            <div className="space-y-2 rounded border border-slate-100 bg-slate-50 p-3">
              <div className="flex flex-wrap items-end gap-2">
                <div className="flex-1">
                  <label className="mb-1 block text-xs text-slate-600" htmlFor="objective-title">
                    عنوان ریزهدف
                  </label>
                  <input
                    id="objective-title"
                    value={draft.title}
                    onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                    className={input}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-600" htmlFor="objective-due">
                    مهلت
                  </label>
                  <JalaliDatePicker id="objective-due" value={draft.due_on} onChange={(iso) => setDraft({ ...draft, due_on: iso ?? "" })} />
                </div>
              </div>
              <div>
                <span className="mb-1 block text-xs text-slate-600">مسئولان</span>
                <ul className="max-h-32 space-y-1 overflow-y-auto rounded border border-slate-200 bg-white p-2">
                  {form.members.map((member) => (
                    <li key={member.user}>
                      <label className="flex items-center gap-2 rounded px-1.5 py-1 text-sm hover:bg-slate-50">
                        <input
                          type="checkbox"
                          checked={draft.assignees.includes(member.user)}
                          onChange={() => toggleDraftAssignee(member.user)}
                        />
                        <span className="truncate">{member.name}</span>
                        <span className="truncate text-xs text-slate-500">{member.title}</span>
                      </label>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="flex items-end justify-end gap-2">
                <button
                  type="button"
                  onClick={addObjective}
                  disabled={!canAddDraftObjective(draft)}
                  className="rounded border border-slate-300 bg-white px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  افزودن
                </button>
              </div>
            </div>
          ) : (
            <p className="text-xs text-slate-500">برای افزودن ریزهدف، ابتدا بخش و دست‌کم یک عضو را انتخاب کنید.</p>
          )}
        </div>

        <button type="submit" disabled={saving} className="w-full rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50">
          {saving ? "در حال ایجاد..." : "ایجاد پروژه"}
        </button>
      </form>
    </div>
  );
}
