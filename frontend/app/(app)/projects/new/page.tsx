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
import { controlClass } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { CalendarClock, Check, FilePenLine, Flag, FolderPlus, ListChecks, Plus, Target, Trash2, Users } from "lucide-react";
import { Avatar, AvatarStack } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { FormSection } from "@/components/ui/FormSection";
import { cardClass } from "@/components/ui/Card";
import { cx } from "@/components/ui/cx";

const input = `${controlClass} w-full px-3 py-2 text-sm`;
const label = "mb-1.5 block text-sm text-slate-700";
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

  const sectionName = sections.find((option) => option.id === form.section)?.label ?? null;
  const fieldError = (message?: string) =>
    message ? <p className="mt-1.5 text-xs text-rose-600 animate-fade-in">{message}</p> : null;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader
        title="پروژهٔ جدید"
        subtitle="بخش، اعضا، هدف و ریزهدف‌ها — همه در یک فرم؛ پیش‌نویس خودکار ذخیره می‌شود."
        back={{ href: "/projects", label: "پروژه‌ها" }}
      />

      {draftState === "banner" && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-amber-200 bg-amber-50/80 px-4 py-3 text-sm text-amber-900 animate-fade-in">
          <span className="flex items-center gap-2">
            <FilePenLine className="size-4 text-amber-600" />
            پیش‌نویس ذخیره‌شده دارید.
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={continueDraft}
              className="inline-flex h-9 items-center rounded-lg bg-amber-600 px-3 text-xs font-bold text-white transition-colors hover:bg-amber-700"
            >
              ادامهٔ پیش‌نویس
            </button>
            <button
              type="button"
              onClick={discardDraft}
              className="inline-flex h-9 items-center rounded-lg border border-amber-300 bg-white px-3 text-xs text-amber-900 transition-colors hover:bg-amber-100"
            >
              شروع از نو
            </button>
          </div>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
        <form onSubmit={handleSubmit} className={cx(cardClass, "overflow-hidden")} noValidate>
          {serverError && (
            <div className="px-5 pt-5 sm:px-6">
              <ErrorBanner message={serverError} />
            </div>
          )}

          <FormSection step={1} title="بخش و نام" description="پروژه در یک بخش از ساختار سازمان تعریف می‌شود.">
            <div>
              <label className={label} htmlFor="section">
                بخش
              </label>
              {sections.length === 0 ? (
                <p className="rounded-xl border border-dashed border-slate-300 px-3 py-3 text-xs text-slate-500">
                  هنوز بخشی در ساختار سازمان تعریف نشده است.
                </p>
              ) : (
                <select
                  id="section"
                  value={form.section ?? ""}
                  onChange={(e) => selectSection(e.target.value ? Number(e.target.value) : null)}
                  className={cx(input, "h-11")}
                >
                  <option value="">انتخاب کنید…</option>
                  {sections.map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.label}
                    </option>
                  ))}
                </select>
              )}
              {fieldError(errors.section)}
            </div>

            <div>
              <label className={label} htmlFor="name">
                نام پروژه
              </label>
              <input
                id="name"
                value={form.name}
                onChange={(e) => set("name", e.target.value)}
                maxLength={255}
                className={cx(input, "h-11")}
              />
              {fieldError(errors.name)}
            </div>
          </FormSection>

          <FormSection step={2} title="اعضای پروژه" description="شما به‌عنوان مدیر پروژه خودکار افزوده می‌شوید.">
            {form.section !== null ? (
              <MemberPicker sectionId={form.section} members={form.members} onChange={applyMembers} />
            ) : (
              <p className="flex items-center gap-2 rounded-xl border border-dashed border-slate-300 px-3 py-3 text-xs text-slate-500">
                <Users className="size-4 text-slate-400" />
                ابتدا بخش را انتخاب کنید.
              </p>
            )}
          </FormSection>

          <FormSection step={3} title="هدف و زمان‌بندی">
            <div>
              <label className={label} htmlFor="goal">
                هدف پروژه
              </label>
              <textarea id="goal" value={form.goal} onChange={(e) => set("goal", e.target.value)} rows={3} className={cx(input, "leading-7")} />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
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
                {fieldError(errors.due_on)}
              </div>
            </div>
          </FormSection>

          <FormSection
            step={4}
            title="برنامه‌ریزی (ریزهدف‌ها)"
            description="کارهایی که پروژه را جلو می‌برند، هر کدام با مسئول و مهلت."
            actions={
              form.objectives.length > 0 && (
                <span className="rounded-full bg-brand-50 px-2.5 py-0.5 text-xs text-brand-800 ring-1 ring-inset ring-brand-600/15 tabular-nums">
                  {form.objectives.length} ریزهدف
                </span>
              )
            }
          >
            {form.objectives.length > 0 && (
              <ol className="space-y-2">
                {form.objectives.map((objective, index) => (
                  <li
                    key={objective.key}
                    className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm animate-fade-in"
                  >
                    <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-bold text-slate-600 tabular-nums">
                      {(index + 1).toLocaleString("fa-IR")}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-bold text-slate-900">{objective.title}</span>
                      <span className="block truncate text-xs text-slate-500">{assigneeNames(objective.assignees)}</span>
                    </span>
                    <span className="hidden shrink-0 items-center gap-1 rounded-full bg-slate-50 px-2 py-0.5 text-xs text-slate-600 ring-1 ring-inset ring-slate-200 sm:inline-flex">
                      <CalendarClock className="size-3.5" />
                      {formatJalali(objective.due_on)}
                    </span>
                    <button
                      type="button"
                      onClick={() => removeObjective(objective.key)}
                      aria-label={`حذف ${objective.title}`}
                      title="حذف"
                      className="flex size-8 shrink-0 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-600"
                    >
                      <Trash2 className="size-4" />
                    </button>
                  </li>
                ))}
              </ol>
            )}

            {form.section !== null && form.members.length > 0 ? (
              <div className="space-y-4 rounded-2xl border border-dashed border-brand-200 bg-brand-50/30 p-4">
                <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_12rem]">
                  <div>
                    <label className="mb-1.5 block text-xs text-slate-600" htmlFor="objective-title">
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
                    <label className="mb-1.5 block text-xs text-slate-600" htmlFor="objective-due">
                      مهلت
                    </label>
                    <JalaliDatePicker id="objective-due" value={draft.due_on} onChange={(iso) => setDraft({ ...draft, due_on: iso ?? "" })} />
                  </div>
                </div>
                <div>
                  <span className="mb-1.5 block text-xs text-slate-600">مسئولان</span>
                  <div className="flex flex-wrap gap-2">
                    {form.members.map((member) => {
                      const on = draft.assignees.includes(member.user);
                      return (
                        <button
                          key={member.user}
                          type="button"
                          aria-pressed={on}
                          onClick={() => toggleDraftAssignee(member.user)}
                          className={cx(
                            "flex items-center gap-2 rounded-full py-1 ps-1 pe-3 text-xs ring-1 ring-inset transition-[background-color,box-shadow] duration-150 active:scale-[0.97]",
                            on ? "bg-brand-700 text-white ring-brand-700" : "bg-white text-slate-700 ring-slate-200 hover:ring-slate-300",
                          )}
                        >
                          {on ? (
                            <span className="flex size-6 items-center justify-center rounded-full bg-white/20">
                              <Check className="size-3.5" />
                            </span>
                          ) : (
                            <Avatar name={member.name} size="xs" />
                          )}
                          {member.name}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <div className="flex justify-end">
                  <Button variant="subtle" icon={<Plus />} onClick={addObjective} disabled={!canAddDraftObjective(draft)}>
                    افزودن ریزهدف
                  </Button>
                </div>
              </div>
            ) : (
              <p className="flex items-center gap-2 rounded-xl border border-dashed border-slate-300 px-3 py-3 text-xs text-slate-500">
                <ListChecks className="size-4 text-slate-400" />
                برای افزودن ریزهدف، ابتدا بخش و دست‌کم یک عضو را انتخاب کنید.
              </p>
            )}
          </FormSection>

          <div className="flex justify-end border-t border-slate-100 bg-slate-50/70 px-5 py-4 sm:px-6">
            <Button type="submit" variant="primary" size="lg" loading={saving} icon={<FolderPlus />} className="min-w-44">
              {saving ? "در حال ایجاد..." : "ایجاد پروژه"}
            </Button>
          </div>
        </form>

        {/* A live summary of the project being built. */}
        <aside aria-label="خلاصهٔ پروژه" className={cx(cardClass, "overflow-hidden lg:sticky lg:top-4")}>
          <div className="relative h-16 overflow-hidden bg-gradient-to-l from-surface to-surface-raised">
            <span aria-hidden className="absolute -top-10 left-1/3 size-36 rounded-full bg-accent/20 blur-2xl" />
          </div>
          <div className="space-y-4 p-5">
            <div>
              <p className="truncate text-lg font-bold text-slate-900">{form.name || "نام پروژه"}</p>
              <p className="truncate text-xs text-slate-500">{sectionName ?? "بخش انتخاب نشده"}</p>
            </div>
            <dl className="space-y-2.5 text-sm">
              <div className="flex items-center justify-between gap-2">
                <dt className="flex items-center gap-2 text-slate-500">
                  <Users className="size-4" />
                  اعضا
                </dt>
                <dd>
                  {form.members.length > 0 ? (
                    <AvatarStack names={form.members.map((m) => m.name)} label={`${form.members.length} عضو`} />
                  ) : (
                    <span className="text-slate-400">—</span>
                  )}
                </dd>
              </div>
              <div className="flex items-center justify-between gap-2">
                <dt className="flex items-center gap-2 text-slate-500">
                  <Flag className="size-4" />
                  شروع
                </dt>
                <dd className="text-slate-800">{form.starts_on ? formatJalali(form.starts_on) : "—"}</dd>
              </div>
              <div className="flex items-center justify-between gap-2">
                <dt className="flex items-center gap-2 text-slate-500">
                  <CalendarClock className="size-4" />
                  مهلت
                </dt>
                <dd className="text-slate-800">{form.due_on ? formatJalali(form.due_on) : "—"}</dd>
              </div>
              <div className="flex items-center justify-between gap-2">
                <dt className="flex items-center gap-2 text-slate-500">
                  <Target className="size-4" />
                  ریزهدف‌ها
                </dt>
                <dd className="font-bold text-slate-800 tabular-nums">{form.objectives.length}</dd>
              </div>
            </dl>
          </div>
        </aside>
      </div>
    </div>
  );
}
