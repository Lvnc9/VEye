"use client";

import { useState, type FormEvent, type KeyboardEvent } from "react";
import { ApiError, apiDelete, apiPost } from "@/lib/api-client";
import { formatJalaliDateTime } from "@/lib/jalali";
import { useCurrentUser } from "@/lib/current-user";
import { draftKey, useLocalDraft } from "@/lib/local-draft";
import type { ProjectComment } from "@/lib/projects";
import type { Paginated } from "@/lib/types";
import { useApiQuery } from "@/lib/use-api-query";
import { ErrorBanner } from "@/components/StatusBanner";
import { SendHorizontal, StickyNote, Trash2 } from "lucide-react";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { IconButton } from "@/components/ui/IconButton";
import { SkeletonLines } from "@/components/ui/Skeleton";

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
    <Card aria-label="یادداشت‌ها">
      <CardHeader
        title="یادداشت‌ها"
        icon={<StickyNote />}
        actions={
          rows.length > 0 && (
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-600 tabular-nums">{rows.length}</span>
          )
        }
      />
      {error && <ErrorBanner message={error} />}
      <form onSubmit={onFormSubmit} className="mb-5 flex items-start gap-3">
        {user && <Avatar name={user.full_name} className="mt-1" />}
        <div className="min-w-0 flex-1 rounded-2xl border border-slate-300 bg-white shadow-xs transition-[border-color,box-shadow] duration-150 focus-within:border-brand-500 focus-within:ring-4 focus-within:ring-brand-500/15">
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="یادداشتی بنویسید… (Ctrl+Enter برای ارسال)"
            aria-label="متن یادداشت"
            maxLength={4000}
            rows={2}
            className="block w-full resize-none rounded-t-2xl bg-transparent px-3.5 pt-3 text-sm leading-7 text-slate-900 placeholder:text-slate-400 focus:outline-none"
          />
          <div className="flex items-center justify-between gap-2 px-2 pb-2">
            <span className="ps-1.5 text-[11px] text-slate-400">Ctrl + Enter</span>
            <Button type="submit" variant="primary" size="sm" icon={<SendHorizontal className="rtl-flip" />} disabled={!body.trim()} loading={posting}>
              ثبت
            </Button>
          </div>
        </div>
      </form>
      {comments.loading ? (
        <SkeletonLines rows={3} />
      ) : comments.error ? (
        <ErrorBanner message={comments.error} />
      ) : rows.length === 0 ? (
        <EmptyState compact icon={<StickyNote />} message="هنوز یادداشتی ثبت نشده است." />
      ) : (
        <ul className="space-y-4">
          {rows.map((comment) => (
            <li key={comment.id} className="group flex items-start gap-3 text-sm animate-fade-in">
              <Avatar name={comment.author_name} size="sm" className="mt-0.5" />
              <div className="min-w-0 flex-1 rounded-2xl rounded-tr-md bg-slate-50 px-3.5 py-2.5 ring-1 ring-inset ring-slate-200/70">
                <p className="flex flex-wrap items-baseline gap-x-2 text-slate-900">
                  <span className="font-bold">{comment.author_name}</span>
                  {comment.author_title && <span className="text-xs text-slate-500">{comment.author_title}</span>}
                  <span className="text-xs text-slate-500">{formatJalaliDateTime(comment.created_at)}</span>
                </p>
                <p className="mt-1 whitespace-pre-wrap leading-7 text-slate-700">{comment.body}</p>
              </div>
              {comment.can_delete && (
                <IconButton
                  label="حذف یادداشت"
                  tone="danger"
                  size="sm"
                  onClick={() => remove(comment.id)}
                  className="opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100 pointer-coarse:opacity-100"
                >
                  <Trash2 />
                </IconButton>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
