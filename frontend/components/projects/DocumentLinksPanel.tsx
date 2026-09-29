"use client";

import { useState } from "react";
import { ApiError, apiDelete, apiPost } from "@/lib/api-client";
import type { ProjectDocumentLink } from "@/lib/projects";
import type { DocumentRow, Paginated } from "@/lib/types";
import { useApiQuery } from "@/lib/use-api-query";
import { ErrorBanner } from "@/components/StatusBanner";
import { buttonClass } from "@/components/ui/Button";
import { controlClass } from "@/components/ui/Field";
import Link from "next/link";
import { Check, FileText, Link2, Search, Unlink } from "lucide-react";
import { Code } from "@/components/Code";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { IconButton } from "@/components/ui/IconButton";
import { SkeletonLines } from "@/components/ui/Skeleton";

/** مستندات پیوست‌شده: VEye is a document system, so a project that produced PR-07 should say so.
 *  Linking (and unlinking) needs the project's own edit rights — the same governance as any other
 *  change to the project's content. */
export function DocumentLinksPanel({ projectId, canEdit }: { projectId: number; canEdit: boolean }) {
  const [reload, setReload] = useState(0);
  const links = useApiQuery<ProjectDocumentLink[]>(`/projects/${projectId}/documents/`, reload);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function unlink(linkId: number) {
    setError(null);
    try {
      await apiDelete(`/projects/${projectId}/documents/${linkId}/`);
      setReload((n) => n + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "حذف پیوند ممکن نشد.");
    }
  }

  async function link(document: DocumentRow) {
    setError(null);
    try {
      await apiPost(`/projects/${projectId}/documents/`, { document: document.id });
      setQuery("");
      setReload((n) => n + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "پیوست مستند ممکن نشد.");
    }
  }

  const rows = links.data ?? [];

  return (
    <Card aria-label="مستندات پیوست‌شده">
      <CardHeader title="مستندات پیوست‌شده" icon={<FileText />} />
      {error && <ErrorBanner message={error} />}
      {links.loading ? (
        <SkeletonLines rows={2} />
      ) : links.error ? (
        <ErrorBanner message={links.error} />
      ) : rows.length === 0 ? (
        <EmptyState compact icon={<FileText />} message="هنوز مستندی به این پروژه پیوست نشده است." />
      ) : (
        <ul className="space-y-2">
          {rows.map((link) => (
            <li
              key={link.id}
              className="group flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm transition-colors hover:border-slate-300"
            >
              <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
                <FileText className="size-4" />
              </span>
              <span className="min-w-0 flex-1">
                <Link href={`/documents/${link.document}/edit`} className="block truncate font-bold text-slate-900 transition-colors hover:text-brand-700">
                  {link.document_title}
                </Link>
                <span className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                  <Code>{link.document_full_code}</Code>
                  {link.caption}
                </span>
              </span>
              {canEdit && (
                <IconButton label="حذف پیوند" tone="danger" size="sm" onClick={() => unlink(link.id)}>
                  <Unlink />
                </IconButton>
              )}
            </li>
          ))}
        </ul>
      )}

      {canEdit && (
        <div className="mt-4 border-t border-slate-100 pt-4">
          <label htmlFor="link-document-search" className="mb-1.5 flex items-center gap-1.5 text-xs text-slate-600">
            <Link2 className="size-3.5" />
            پیوست مستند
          </label>
          <div className="relative">
            <Search className="pointer-events-none absolute inset-y-0 right-3 my-auto size-4 text-slate-400" />
            <input
              id="link-document-search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="جست و جوی عنوان یا کد مستند"
              className={`${controlClass} h-10 w-full pr-9 pl-3 text-sm`}
            />
          </div>
          {query.trim().length >= 2 && (
            <DocumentResults key={query} query={query} linkedIds={new Set(rows.map((r) => r.document))} onLink={link} />
          )}
        </div>
      )}
    </Card>
  );
}

function DocumentResults({ query, linkedIds, onLink }: { query: string; linkedIds: Set<number>; onLink: (document: DocumentRow) => void }) {
  const documents = useApiQuery<Paginated<DocumentRow>>(`/documents/?search=${encodeURIComponent(query)}&page_size=8`);
  if (documents.loading) return <p className="mt-2 text-xs text-slate-500">در حال جستجو...</p>;
  if (documents.error) return <p className="mt-1 text-xs text-rose-600">{documents.error}</p>;
  const rows = documents.data?.results ?? [];
  if (rows.length === 0) return <p className="mt-1 text-xs text-slate-500">مستندی پیدا نشد.</p>;
  return (
    <ul className="mt-2 space-y-1.5 animate-fade-in">
      {rows.map((document) => {
        const already = linkedIds.has(document.id);
        return (
          <li key={document.id} className="flex items-center justify-between gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm transition-colors hover:border-slate-300">
            <span className="flex min-w-0 items-center gap-2">
              <Code>{document.full_code}</Code>
              <span className="truncate">{document.title}</span>
            </span>
            <button
              type="button"
              disabled={already}
              onClick={() => onLink(document)}
              className={buttonClass({ variant: "secondary", size: "xs", className: "shrink-0" })}
            >
              {already ? <Check /> : <Link2 />}
              {already ? "پیوست شد" : "پیوست"}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
