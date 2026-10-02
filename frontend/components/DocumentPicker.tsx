"use client";

import { useState, type ReactNode } from "react";
import type { DocumentRow, Paginated } from "@/lib/types";
import { useApiQuery } from "@/lib/use-api-query";
import { Code } from "@/components/Code";
import { buttonClass } from "@/components/ui/Button";
import { controlClass } from "@/components/ui/Field";
import { Check, Link2, Search } from "lucide-react";

/**
 * Find a document by title or code and pick it: a search box and, from two letters on, the matching
 * documents (`GET /documents/?search=`), each with a button. Was private to the project's document
 * links panel before the quality module needed the same thing for «مستند مرتبط».
 *
 * The box clears itself after a pick; documents in `excludedIds` stay listed with the button disabled
 * and labelled `doneLabel`, so it is clear why they cannot be picked again.
 */
export function DocumentPicker({
  id,
  label,
  placeholder = "جست و جوی عنوان یا کد مستند",
  excludedIds,
  onPick,
  pickLabel = "پیوست",
  doneLabel = "پیوست شد",
}: {
  id: string;
  label: ReactNode;
  placeholder?: string;
  excludedIds?: ReadonlySet<number>;
  onPick: (document: DocumentRow) => void;
  pickLabel?: string;
  doneLabel?: string;
}) {
  const [query, setQuery] = useState("");

  return (
    <div>
      <label htmlFor={id} className="mb-1.5 flex items-center gap-1.5 text-xs text-slate-600">
        {label}
      </label>
      <div className="relative">
        <Search className="pointer-events-none absolute inset-y-0 right-3 my-auto size-4 text-slate-400" />
        <input
          id={id}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder}
          className={`${controlClass} h-10 w-full pr-9 pl-3 text-sm`}
        />
      </div>
      {query.trim().length >= 2 && (
        <DocumentResults
          key={query}
          query={query}
          excludedIds={excludedIds}
          pickLabel={pickLabel}
          doneLabel={doneLabel}
          onPick={(document) => {
            setQuery("");
            onPick(document);
          }}
        />
      )}
    </div>
  );
}

function DocumentResults({
  query,
  excludedIds,
  pickLabel,
  doneLabel,
  onPick,
}: {
  query: string;
  excludedIds?: ReadonlySet<number>;
  pickLabel: string;
  doneLabel: string;
  onPick: (document: DocumentRow) => void;
}) {
  const documents = useApiQuery<Paginated<DocumentRow>>(`/documents/?search=${encodeURIComponent(query)}&page_size=8`);
  if (documents.loading) return <p className="mt-2 text-xs text-slate-500">در حال جستجو...</p>;
  if (documents.error) return <p className="mt-1 text-xs text-rose-600">{documents.error}</p>;
  const rows = documents.data?.results ?? [];
  if (rows.length === 0) return <p className="mt-1 text-xs text-slate-500">مستندی پیدا نشد.</p>;
  return (
    <ul className="mt-2 space-y-1.5 animate-fade-in">
      {rows.map((document) => {
        const already = excludedIds?.has(document.id) ?? false;
        return (
          <li key={document.id} className="flex items-center justify-between gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm transition-colors hover:border-slate-300">
            <span className="flex min-w-0 items-center gap-2">
              <Code>{document.full_code}</Code>
              <span className="truncate">{document.title}</span>
            </span>
            <button
              type="button"
              disabled={already}
              onClick={() => onPick(document)}
              className={buttonClass({ variant: "secondary", size: "xs", className: "shrink-0" })}
            >
              {already ? <Check /> : <Link2 />}
              {already ? doneLabel : pickLabel}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
