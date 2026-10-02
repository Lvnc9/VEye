"use client";

import { useState } from "react";
import { ApiError, apiDelete, apiPost } from "@/lib/api-client";
import type { ProjectDocumentLink } from "@/lib/projects";
import type { DocumentRow } from "@/lib/types";
import { useApiQuery } from "@/lib/use-api-query";
import { DocumentPicker } from "@/components/DocumentPicker";
import { ErrorBanner } from "@/components/StatusBanner";
import Link from "next/link";
import { FileText, Link2, Unlink } from "lucide-react";
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
          <DocumentPicker
            id="link-document-search"
            label={
              <>
                <Link2 className="size-3.5" />
                پیوست مستند
              </>
            }
            excludedIds={new Set(rows.map((r) => r.document))}
            onPick={link}
          />
        </div>
      )}
    </Card>
  );
}
