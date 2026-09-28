"use client";

import { useState, type FormEvent, type KeyboardEvent } from "react";
import { ApiError, apiDelete, apiPost } from "@/lib/api-client";
import { formatJalaliDateTime } from "@/lib/jalali";
import { useCurrentUser } from "@/lib/current-user";
import { draftKey, useLocalDraft } from "@/lib/local-draft";
import type { ProjectComment } from "@/lib/projects";
import type { Paginated } from "@/lib/types";
import { useApiQuery } from "@/lib/use-api-query";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
import { buttonClass } from "@/components/ui/Button";
import { controlClass } from "@/components/ui/Field";

/** یادداشت‌های پروژه: anyone who can read the project may post; only a comment's own author may
 *  ever delete it (backend enforces this — `can_delete` here only decides whether to show the
 *  button). Append-only: no editing. Rendered as a vertical timeline — a dot per note, joined by a
 *  continuous line on the start (right) side, plain CSS. */
export function CommentsPanel({ projectId }: { projectId: number }) {
  const { user } = useCurrentUser();
  const [reload, setReload] = useState(0);
  const comments = useApiQuery<Paginated<ProjectComment>>(`/projects/${projectId}/comments/?page_size=50`, reload);
  const [body, setBody, clearBody] = useLocalDraft(user ? draftKey(user.id, projectId, "note") : null);
  const [error, setError] = useState<string | null>(null);
  const [posting, setPosting] = useState(false);

  async function submit() {
    if (!body.trim()) return;
    setPosting(true);
    setError(null);
    try {
      await apiPost(`/projects/${projectId}/comments/`, { body: body.trim() });
      clearBody();
      setReload((n) => n + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ثبت یادداشت ممکن نشد.");
    } finally {
      setPosting(false);
    }
  }

  function onFormSubmit(event: FormEvent) {
    event.preventDefault();
    submit();
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      submit();
    }
  }

  async function remove(commentId: number) {
    setError(null);
    try {
      await apiDelete(`/projects/${projectId}/comments/${commentId}/`);
      setReload((n) => n + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "حذف یادداشت ممکن نشد.");
    }
  }

  const rows = comments.data?.results ?? [];

  return (
    <section aria-label="یادداشت‌ها" className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card sm:p-6">
      <h2 className="mb-4 text-base font-bold text-slate-900">یادداشت‌ها</h2>
      {error && <ErrorBanner message={error} />}
      <form onSubmit={onFormSubmit} className="mb-4 space-y-2">
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="یادداشتی بنویسید… (Ctrl+Enter برای ارسال)"
          aria-label="متن یادداشت"
          maxLength={4000}
          rows={2}
          className={`${controlClass} w-full px-3 py-2 text-sm`}
        />
        <div className="flex justify-end">
          <button type="submit" disabled={posting || !body.trim()} className={buttonClass({ variant: "primary", size: "md" })}>
            ثبت
          </button>
        </div>
      </form>
      {comments.loading ? (
        <LoadingBanner />
      ) : comments.error ? (
        <ErrorBanner message={comments.error} />
      ) : rows.length === 0 ? (
        <p className="text-sm text-slate-500">هنوز یادداشتی ثبت نشده است.</p>
      ) : (
        <ul className="relative space-y-4 border-s-2 border-slate-200 ps-4">
          {rows.map((comment) => (
            <li key={comment.id} className="relative flex items-start justify-between gap-2 text-sm">
              <span aria-hidden className="absolute -start-[1.15rem] top-1 h-2.5 w-2.5 rounded-full bg-slate-400 ring-4 ring-white" />
              <div className="min-w-0">
                <p className="font-medium text-slate-900">
                  {comment.author_name}
                  {comment.author_title && <span className="font-normal text-slate-500"> ({comment.author_title})</span>}
                  <span className="mr-2 text-xs text-slate-400">{formatJalaliDateTime(comment.created_at)}</span>
                </p>
                <p className="mt-0.5 whitespace-pre-wrap text-slate-700">{comment.body}</p>
              </div>
              {comment.can_delete && (
                <button
                  type="button"
                  onClick={() => remove(comment.id)}
                  aria-label="حذف یادداشت"
                  className="shrink-0 rounded-md px-1.5 py-0.5 text-xs text-rose-600 transition-colors hover:bg-rose-50"
                >
                  حذف
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
