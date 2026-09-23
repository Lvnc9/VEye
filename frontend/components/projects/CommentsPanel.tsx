"use client";

import { useState, type FormEvent } from "react";
import { ApiError, apiDelete, apiPost } from "@/lib/api-client";
import { formatJalaliDateTime } from "@/lib/jalali";
import type { ProjectComment } from "@/lib/projects";
import type { Paginated } from "@/lib/types";
import { useApiQuery } from "@/lib/use-api-query";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";

/** یادداشت‌های پروژه: anyone who can read the project may post; only a comment's own author may
 *  ever delete it (backend enforces this — `can_delete` here only decides whether to show the
 *  button). Append-only: no editing. */
export function CommentsPanel({ projectId }: { projectId: number }) {
  const [reload, setReload] = useState(0);
  const comments = useApiQuery<Paginated<ProjectComment>>(`/projects/${projectId}/comments/?page_size=50`, reload);
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [posting, setPosting] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!body.trim()) return;
    setPosting(true);
    setError(null);
    try {
      await apiPost(`/projects/${projectId}/comments/`, { body: body.trim() });
      setBody("");
      setReload((n) => n + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ثبت یادداشت ممکن نشد.");
    } finally {
      setPosting(false);
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
    <section aria-label="یادداشت‌ها" className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="mb-3 text-base font-semibold text-slate-900">یادداشت‌ها</h2>
      {error && <ErrorBanner message={error} />}
      <form onSubmit={submit} className="mb-4 flex gap-2">
        <input
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="یادداشتی بنویسید…"
          aria-label="متن یادداشت"
          maxLength={4000}
          className="flex-1 rounded border border-slate-300 bg-white px-3 py-2 text-sm"
        />
        <button type="submit" disabled={posting || !body.trim()} className="rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50">
          ثبت
        </button>
      </form>
      {comments.loading ? (
        <LoadingBanner />
      ) : comments.error ? (
        <ErrorBanner message={comments.error} />
      ) : rows.length === 0 ? (
        <p className="text-sm text-slate-500">هنوز یادداشتی ثبت نشده است.</p>
      ) : (
        <ul className="space-y-3">
          {rows.map((comment) => (
            <li key={comment.id} className="flex items-start justify-between gap-2 text-sm">
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
                  className="shrink-0 text-xs text-red-600 hover:underline"
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
