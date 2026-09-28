"use client";

import { useEffect, useState } from "react";
import { ApiError, apiGet } from "@/lib/api-client";
import type { AttachmentTarget, DocumentRow, Paginated } from "@/lib/types";
import { Code } from "../Code";
import { StatusBadge } from "../StatusBadge";
import { inputClass } from "./ui";
import { Search, SearchX } from "lucide-react";
import { Dialog } from "@/components/ui/Dialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { SkeletonLines } from "@/components/ui/Skeleton";

const LIMIT = 8;

/**
 * Choose the document an attachment points at.
 *
 * V_1.0 did this by *leaving the designer* for the register in a "select" mode
 * (yellow Select buttons), then reloading the half-edited document from its saved
 * JSON when you came back (poster_01.py:632-643, utils.py:250-384). A modal over
 * the same list endpoint means nothing is lost by choosing one.
 */
export function DocumentPicker({
  excludeId,
  onSelect,
  onClose,
}: {
  /** The document being edited — it can't attach itself. */
  excludeId: number;
  onSelect: (target: AttachmentTarget) => void;
  onClose: () => void;
}) {
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<DocumentRow[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(() => {
      setLoading(true);
      apiGet<Paginated<DocumentRow>>("/documents/", { search, page_size: LIMIT + 1 })
        .then((response) => {
          if (cancelled) return;
          setResults(response.results.filter((row) => row.id !== excludeId).slice(0, LIMIT));
          setCount(response.count);
          setError(null);
        })
        .catch((err) => {
          if (!cancelled) setError(err instanceof ApiError ? err.message : "دریافت فهرست مستندات ممکن نشد.");
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [search, excludeId]);

  return (
    <Dialog label="انتخاب مستند" title="انتخاب مستند ضمیمه" onClose={onClose} size="lg">
      <div className="relative">
        <Search className="pointer-events-none absolute inset-y-0 right-3 my-auto size-4 text-slate-400" />
        <input
          type="search"
          autoFocus
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="جست و جو — عنوان یا کد مستند"
          aria-label="جست و جوی مستند"
          className={`${inputClass} pr-9`}
        />
      </div>

      <div className="max-h-80 overflow-y-auto">
        {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
        {!error && loading && results.length === 0 && (
          <div role="status" className="space-y-3 py-2">
            <p className="text-sm text-slate-500">در حال جست و جو...</p>
            <SkeletonLines rows={3} />
          </div>
        )}
        {!error && !loading && results.length === 0 && (
          <EmptyState compact icon={<SearchX />} message="مستندی یافت نشد." />
        )}
        <ul className="space-y-1">
          {results.map((row) => (
            <li key={row.id}>
              <button
                type="button"
                onClick={() =>
                  onSelect({
                    id: row.id,
                    full_code: row.full_code,
                    title: row.title,
                    status: row.status,
                    status_label: row.status_label,
                  })
                }
                className="flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-right transition-colors hover:bg-brand-50/70"
              >
                <span className="flex min-w-0 items-center gap-3">
                  <Code>{row.full_code}</Code>
                  <span className="truncate text-sm text-slate-800">{row.title}</span>
                </span>
                <StatusBadge status={row.status} label={row.status_label} />
              </button>
            </li>
          ))}
        </ul>
        {count > LIMIT + 1 && (
          <p className="pt-3 text-center text-xs text-slate-400">نتایج بیشتری هست — جست و جو را دقیق‌تر کنید.</p>
        )}
      </div>
    </Dialog>
  );
}
