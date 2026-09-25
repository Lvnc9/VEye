"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ApiError, apiPost } from "@/lib/api-client";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
import { JalaliDatePicker } from "@/components/JalaliDatePicker";
import { MemberPicker } from "@/components/projects/MemberPicker";
import { formatJalali } from "@/lib/jalali";
import { nodeOptions, type OrgTreeResponse } from "@/lib/organization";
import {
  EMPTY_CREATE_FORM,
  canAddDraftObjective,
  createProjectBody,
  validateCreateForm,
  type CreateErrors,
  type DraftObjective,
  type Project,
  type ProjectCreateForm,
} from "@/lib/projects";
import { useApiQuery } from "@/lib/use-api-query";

const input = "w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm";
const label = "mb-1 block text-sm font-medium text-slate-700";

function emptyDraft(): DraftObjective {
  return { key: crypto.randomUUID(), title: "", assignee: null, assigneeName: "", due_on: "", weight: 1 };
}

/** ایجاد پروژه (docs/11 §3.5): one page, four blocks, submitted as one `POST /projects/` with a
 *  nested `objectives` array — a half-created project is impossible. */
export default function NewProjectPage() {
  const router = useRouter();
  const tree = useApiQuery<OrgTreeResponse>("/org/tree/");
  const [form, setForm] = useState<ProjectCreateForm>(EMPTY_CREATE_FORM);
  const [draft, setDraft] = useState<DraftObjective>(emptyDraft());
  const [errors, setErrors] = useState<CreateErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const set = <K extends keyof ProjectCreateForm>(key: K, value: ProjectCreateForm[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  function addObjective() {
    if (!canAddDraftObjective(draft)) return;
    setForm((f) => ({ ...f, objectives: [...f.objectives, draft] }));
    setDraft(emptyDraft());
  }

  function removeObjective(key: string) {
    setForm((f) => ({ ...f, objectives: f.objectives.filter((o) => o.key !== key) }));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const found = validateCreateForm(form);
    setErrors(found);
    setServerError(null);
    if (Object.keys(found).length > 0) return;

    setSaving(true);
    try {
      const project = await apiPost<Project>("/projects/", createProjectBody(form));
      router.push(`/projects/${project.id}`);
    } catch (err) {
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
              onChange={(e) => {
                set("section", e.target.value ? Number(e.target.value) : null);
                set("members", []);
              }}
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
            <MemberPicker sectionId={form.section} members={form.members} onChange={(members) => set("members", members)} />
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
                    {objective.title} — {objective.assigneeName} — {formatJalali(objective.due_on)}
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
                <label className="mb-1 block text-xs text-slate-600" htmlFor="objective-assignee">
                  مسئول
                </label>
                <select
                  id="objective-assignee"
                  value={draft.assignee ?? ""}
                  onChange={(e) => {
                    const user = Number(e.target.value);
                    const found = form.members.find((m) => m.user === user);
                    setDraft({ ...draft, assignee: user || null, assigneeName: found?.name ?? "" });
                  }}
                  className={input}
                >
                  <option value="">انتخاب کنید…</option>
                  {form.members.map((member) => (
                    <option key={member.user} value={member.user}>
                      {member.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs text-slate-600" htmlFor="objective-due">
                  مهلت
                </label>
                <JalaliDatePicker
                  id="objective-due"
                  value={draft.due_on}
                  onChange={(iso) => setDraft({ ...draft, due_on: iso ?? "" })}
                />
              </div>
              <button
                type="button"
                onClick={addObjective}
                disabled={!canAddDraftObjective(draft)}
                className="rounded border border-slate-300 bg-white px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                افزودن
              </button>
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
