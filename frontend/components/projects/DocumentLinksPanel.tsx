"use client";

import { useState } from "react";
import { ApiError, apiDelete, apiPost } from "@/lib/api-client";
import type { ProjectDocumentLink } from "@/lib/projects";
import type { DocumentRow, Paginated } from "@/lib/types";
import { useApiQuery } from "@/lib/use-api-query";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";

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
    <section aria-label="مستندات پیوست‌شده" className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="mb-3 text-base font-semibold text-slate-900">مستندات پیوست‌شده</h2>
      {error && <ErrorBanner message={error} />}
      {links.loading ? (
        <LoadingBanner />
      ) : links.error ? (
        <ErrorBanner message={links.error} />
      ) : rows.length === 0 ? (
        <p className="text-sm text-slate-500">هنوز مستندی به این پروژه پیوست نشده است.</p>
      ) : (
        <ul className="space-y-1.5">
          {rows.map((link) => (
            <li key={link.id} className="flex items-center justify-between gap-2 rounded border border-slate-100 px-3 py-1.5 text-sm">
              <span className="min-w-0 truncate">
                <span className="latn ml-1">{link.document_full_code}</span>
                {link.document_title}
                {link.caption && <span className="text-xs text-slate-500"> — {link.caption}</span>}
              </span>
              {canEdit && (
                <button type="button" onClick={() => unlink(link.id)} className="shrink-0 text-xs text-red-600 hover:underline">
                  حذف پیوند
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {canEdit && (
        <div className="mt-3 border-t border-slate-100 pt-3">
          <label htmlFor="link-document-search" className="mb-1 block text-xs font-medium text-slate-600">
            پیوست مستند
          </label>
          <input
            id="link-document-search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="جست و جوی عنوان یا کد مستند"
            className="w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm"
          />
          {query.trim().length >= 2 && (
            <DocumentResults key={query} query={query} linkedIds={new Set(rows.map((r) => r.document))} onLink={link} />
          )}
        </div>
      )}
    </section>
  );
}

function DocumentResults({ query, linkedIds, onLink }: { query: string; linkedIds: Set<number>; onLink: (document: DocumentRow) => void }) {
  const documents = useApiQuery<Paginated<DocumentRow>>(`/documents/?search=${encodeURIComponent(query)}&page_size=8`);
  if (documents.loading) return <p className="mt-1 text-xs text-slate-500">در حال جستجو...</p>;
  if (documents.error) return <p className="mt-1 text-xs text-red-600">{documents.error}</p>;
  const rows = documents.data?.results ?? [];
  if (rows.length === 0) return <p className="mt-1 text-xs text-slate-500">مستندی پیدا نشد.</p>;
  return (
    <ul className="mt-1 space-y-1">
      {rows.map((document) => {
        const already = linkedIds.has(document.id);
        return (
          <li key={document.id} className="flex items-center justify-between gap-2 rounded border border-slate-100 px-3 py-1.5 text-sm">
            <span className="min-w-0 truncate">
              <span className="latn ml-1">{document.full_code}</span>
              {document.title}
            </span>
            <button
              type="button"
              disabled={already}
              onClick={() => onLink(document)}
              className="shrink-0 rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              {already ? "پیوست شد" : "پیوست"}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
