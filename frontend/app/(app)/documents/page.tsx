"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { apiGet, apiPost, ApiError } from "@/lib/api-client";
import { PdfBuildError, buildPdf, followPdf, openPdfInTab, readPdfState } from "@/lib/pdf";
import { takeFlash } from "@/lib/flash";
import {
  DOCUMENT_ACTION_LABELS,
  DOCUMENT_CATEGORY_LABELS,
  DOCUMENT_GROUP_LABELS,
  DOCUMENT_STATUS_LABELS,
  type DocumentCategory,
  type DocumentCreatePayload,
  type DocumentFilters,
  type DocumentGroup,
  type DocumentRow,
  type DocumentStatus,
  type Paginated,
  type PdfStatus,
  type ResponsibilityPair,
  type SignOffSummary,
} from "@/lib/types";
import { useCurrentUser } from "@/lib/current-user";
import { EmptyBanner, ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
import { Code } from "@/components/Code";
import { PdfActions } from "@/components/PdfActions";
import { WorkflowActions } from "@/components/WorkflowActions";
import { BulkPrintDialog } from "@/components/BulkPrintDialog";
import { selectionLabel, type BulkSelection } from "@/lib/bulk-print";
import { formatJalali } from "@/lib/jalali";
import { StatusBadge } from "@/components/StatusBadge";

const PAGE_SIZE = 25;

/** The register's columns, in V_1.0's order (documents_01.py:1665-2236). In an
 *  RTL table the first one sits at the right edge. */
const COLUMNS = [
  "ردیف",
  "دسته بندی",
  "عنوان",
  "گروه",
  "بازنگری",
  "کد",
  "حسابکش",
  "پاسخ خواه",
  "پاسخگو",
  "تدوین",
  "تائید",
  "تصویب",
  "وضعیت",
];

function messageOf(err: unknown, fallback: string): string {
  return err instanceof ApiError || err instanceof PdfBuildError ? err.message : fallback;
}

// A stable empty list: `rows` feeds an effect, so a fresh [] each render would re-run it.
const NO_ROWS: DocumentRow[] = [];

const EMPTY_FILTERS: Required<DocumentFilters> = {
  search: "",
  group: "",
  category: "",
  status: "",
};

function SignOffCell({ signoff }: { signoff: SignOffSummary | null }) {
  if (!signoff?.name) return <span className="text-slate-300">—</span>;
  return (
    <span title={signoff.position}>
      {signoff.name}
      {signoff.signed_date && <span className="block text-xs text-slate-400">{formatJalali(signoff.signed_date)}</span>}
    </span>
  );
}

function ResponsibilityCell({ pair }: { pair: ResponsibilityPair | null }) {
  if (!pair) return <span className="text-slate-300">—</span>;
  return (
    <span title={`ناظر: ${pair.supervisor}`}>
      {pair.post}
    </span>
  );
}

export default function DocumentRegisterPage() {
  const { can } = useCurrentUser();
  const canCreate = can("create_document");
  const canPrint = can("print_document");

  // "last" is DRF's own page alias; it lets a fresh document be shown without
  // first having to ask how many pages there are.
  const [page, setPage] = useState<number | "last">(1);
  const [filters, setFilters] = useState<Required<DocumentFilters>>(EMPTY_FILTERS);
  const [searchInput, setSearchInput] = useState("");
  const [reloadToken, setReloadToken] = useState(0);

  const [notice, setNotice] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // A message left by the designer («مستند … ذخیره شد») — read once, after mount.
  // Deferred to a microtask: this project's lint config forbids a synchronous
  // setState in an effect (and reading storage during render would mismatch SSR).
  useEffect(() => {
    void Promise.resolve().then(() => {
      const message = takeFlash();
      if (message) setNotice(message);
    });
  }, []);

  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<{ category: DocumentCategory | ""; title: string; group: DocumentGroup | "" }>({
    category: "",
    title: "",
    group: "",
  });
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [existingTitle, setExistingTitle] = useState<string | null>(null);
  const [revisingId, setRevisingId] = useState<number | null>(null);

  // The official PDF's state as this page last saw it, per row. A build started
  // (or followed) here is newer than what the list loaded with.
  const [pdfStatus, setPdfStatus] = useState<Record<number, PdfStatus>>({});
  const [previewingId, setPreviewingId] = useState<number | null>(null);
  const following = useRef(new Set<number>());

  // چاپ لیست: the rows ticked for bulk print. Tied to the filters they were ticked
  // under — change the filters and the selection reads as empty (derived, no effect).
  const filterSig = JSON.stringify(filters);
  const [selection, setSelection] = useState<{ sig: string; ids: number[] }>({ sig: "", ids: [] });
  const selectedIds = selection.sig === filterSig ? selection.ids : [];
  const [bulkOpen, setBulkOpen] = useState(false);

  // Debounce the search box so typing doesn't fire a request per keystroke.
  // Only acts when the input differs from the applied filter — otherwise a
  // programmatic reset (showNewest, "show existing") would have its page
  // jump undone by a timer firing 300ms later.
  useEffect(() => {
    if (searchInput === filters.search) return;
    const timer = setTimeout(() => {
      setFilters((current) => ({ ...current, search: searchInput }));
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput, filters.search]);

  // `loading` is derived — "the request for the current inputs hasn't come back
  // yet" — rather than set at the start of the effect, so state is only ever
  // written from the async callbacks. The previous page's rows stay visible
  // (dimmed) until the new ones arrive.
  const requestKey = JSON.stringify({ page, filters, reloadToken });
  const [loaded, setLoaded] = useState<{
    key: string;
    rows: DocumentRow[];
    count: number;
    error: string | null;
  } | null>(null);
  const loading = loaded?.key !== requestKey;
  const rows = loaded?.rows ?? NO_ROWS;
  const count = loaded?.count ?? 0;
  const error = loaded?.error ?? null;

  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));
  const currentPage = page === "last" ? totalPages : Math.min(page, totalPages);

  useEffect(() => {
    let cancelled = false;
    apiGet<Paginated<DocumentRow>>("/documents/", {
      page,
      page_size: PAGE_SIZE,
      search: filters.search,
      group: filters.group,
      category: filters.category,
      status: filters.status,
    })
      .then((response) => {
        if (cancelled) return;
        setLoaded({ key: requestKey, rows: response.results, count: response.count, error: null });
      })
      .catch((err) => {
        if (cancelled) return;
        // A stale page number (the list shrank under us) — start over.
        if (err instanceof ApiError && err.status === 404 && page !== 1) {
          setPage(1);
          return;
        }
        setLoaded({
          key: requestKey,
          rows: [],
          count: 0,
          error: err instanceof ApiError ? err.message : "دریافت فهرست مستندات ممکن نشد.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [requestKey, page, filters]);

  function updateFilter<K extends keyof DocumentFilters>(key: K, value: Required<DocumentFilters>[K]) {
    setFilters((current) => ({ ...current, [key]: value }));
    setPage(1);
  }

  function showNewest() {
    setFilters(EMPTY_FILTERS);
    setSearchInput("");
    setPage("last");
    setReloadToken((n) => n + 1);
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreateError(null);
    setExistingTitle(null);
    setNotice(null);
    setCreating(true);
    try {
      const created = await apiPost<DocumentRow>("/documents/", form as DocumentCreatePayload);
      setNotice(`مستند ${created.full_code} ثبت شد.`);
      setForm((current) => ({ ...current, title: "" }));
      showNewest();
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : "ثبت مستند ممکن نشد.");
      const data = err instanceof ApiError ? (err.data as { code?: string } | undefined) : undefined;
      if (data?.code === "title_exists") setExistingTitle(form.title);
    } finally {
      setCreating(false);
    }
  }

  async function handleRevise(row: DocumentRow) {
    setActionError(null);
    setNotice(null);
    setRevisingId(row.id);
    try {
      const created = await apiPost<DocumentRow>(`/documents/${row.id}/revise/`);
      setNotice(`بازنگری ${created.full_code} ایجاد شد.`);
      showNewest();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "ایجاد بازنگری ممکن نشد.");
    } finally {
      setRevisingId(null);
    }
  }

  const setStatus = (id: number, status: PdfStatus) => setPdfStatus((current) => ({ ...current, [id]: status }));

  // A row that loads as "building" (someone started it, or the page was
  // reloaded mid-build) is followed until it settles.
  useEffect(() => {
    for (const row of rows) {
      if (row.pdf_status !== "building" || following.current.has(row.id)) continue;
      following.current.add(row.id);
      followPdf(row.id, "official")
        .then((state) => setStatus(row.id, state.status))
        .catch(() => undefined) // the next reload shows the truth
        .finally(() => following.current.delete(row.id));
    }
  }, [rows]);

  async function runOfficialBuild(row: DocumentRow) {
    setActionError(null);
    setNotice(null);
    following.current.add(row.id);
    setStatus(row.id, "building");
    try {
      await buildPdf(row.id, "official");
      setStatus(row.id, "ready");
      setNotice(`PDF مستند ${row.full_code} آماده شد.`);
    } catch (err) {
      setStatus(row.id, err instanceof PdfBuildError ? "failed" : row.pdf_status);
      setActionError(messageOf(err, "ساخت PDF ممکن نشد."));
    } finally {
      following.current.delete(row.id);
    }
  }

  function handlePrint(row: DocumentRow) {
    const status = pdfStatus[row.id] ?? row.pdf_status;
    if (status === "building") return;
    if (status !== "ready") {
      void runOfficialBuild(row);
      return;
    }
    setActionError(null);
    // Reading the state first also refreshes an expired session before the new
    // tab makes its own cookie-only request for the file.
    openPdfInTab(() => readPdfState(row.id, "official")).catch((err) =>
      setActionError(messageOf(err, "باز کردن PDF ممکن نشد.")),
    );
  }

  function handlePreview(row: DocumentRow) {
    setActionError(null);
    setPreviewingId(row.id);
    openPdfInTab(() => buildPdf(row.id, "preview"))
      .catch((err) => setActionError(messageOf(err, "ساخت پیش‌نمایش ممکن نشد.")))
      .finally(() => setPreviewingId(null));
  }

  const filtersActive = Boolean(filters.search || filters.group || filters.category || filters.status);

  function toggleSelected(id: number) {
    setSelection({
      sig: filterSig,
      ids: selectedIds.includes(id) ? selectedIds.filter((x) => x !== id) : [...selectedIds, id],
    });
  }
  const pageIds = rows.map((row) => row.id);
  const pageAllSelected = pageIds.length > 0 && pageIds.every((id) => selectedIds.includes(id));
  function togglePage() {
    setSelection({
      sig: filterSig,
      ids: pageAllSelected
        ? selectedIds.filter((id) => !pageIds.includes(id))
        : Array.from(new Set([...selectedIds, ...pageIds])),
    });
  }
  const bulkSelection: BulkSelection = selectedIds.length > 0 ? { ids: selectedIds } : { filters };
  const selectClass = "rounded border border-slate-300 bg-white px-3 py-2 text-sm";

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">مستندات سیستم</h1>
          <p className="mt-1 text-sm text-slate-500">ساخت و پیگیری مستندات کنترل‌شده</p>
        </div>
        {canCreate && (
          <button
            type="button"
            onClick={() => setShowCreate((open) => !open)}
            className="rounded bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700"
          >
            {showCreate ? "بستن" : "ایجاد+"}
          </button>
        )}
      </header>

      {canCreate && showCreate && (
        <form
          onSubmit={handleCreate}
          className="space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
        >
          <h2 className="text-lg font-semibold text-slate-900">ثبت مستند جدید</h2>
          {createError && (
            <div className="space-y-2">
              <ErrorBanner message={createError} />
              {existingTitle && (
                <button
                  type="button"
                  onClick={() => {
                    setSearchInput(existingTitle);
                    setFilters({ ...EMPTY_FILTERS, search: existingTitle });
                    setPage(1);
                  }}
                  className="text-sm font-medium text-slate-700 underline"
                >
                  نمایش مستند موجود
                </button>
              )}
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-3">
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700">دسته بندی</span>
              <select
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value as DocumentCategory | "" })}
                className={`${selectClass} w-full`}
              >
                <option value="">انتخاب کنید</option>
                {(Object.keys(DOCUMENT_CATEGORY_LABELS) as DocumentCategory[]).map((value) => (
                  <option key={value} value={value}>
                    {DOCUMENT_CATEGORY_LABELS[value]}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700">عنوان</span>
              <input
                type="text"
                value={form.title}
                maxLength={255}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                className={`${selectClass} w-full`}
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700">گروه</span>
              <select
                value={form.group}
                onChange={(e) => setForm({ ...form, group: e.target.value as DocumentGroup | "" })}
                className={`${selectClass} w-full`}
              >
                <option value="">انتخاب کنید</option>
                {(Object.keys(DOCUMENT_GROUP_LABELS) as DocumentGroup[]).map((value) => (
                  <option key={value} value={value}>
                    {DOCUMENT_GROUP_LABELS[value]}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <button
            type="submit"
            disabled={creating}
            className="rounded bg-slate-900 px-5 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {creating ? "در حال ثبت..." : "ساخت"}
          </button>
        </form>
      )}

      {notice && (
        <div className="rounded border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">{notice}</div>
      )}
      {actionError && <ErrorBanner message={actionError} />}

      <section className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder="جست و جو — مثال: برون سازمانی"
          className="w-full max-w-xs rounded border border-slate-300 bg-white px-3 py-2 text-sm"
        />
        <select value={filters.group} onChange={(e) => updateFilter("group", e.target.value as DocumentGroup | "")} className={selectClass}>
          <option value="">همه گروه‌ها</option>
          {(Object.keys(DOCUMENT_GROUP_LABELS) as DocumentGroup[]).map((value) => (
            <option key={value} value={value}>
              {DOCUMENT_GROUP_LABELS[value]}
            </option>
          ))}
        </select>
        <select value={filters.category} onChange={(e) => updateFilter("category", e.target.value as DocumentCategory | "")} className={selectClass}>
          <option value="">همه دسته‌ها</option>
          {(Object.keys(DOCUMENT_CATEGORY_LABELS) as DocumentCategory[]).map((value) => (
            <option key={value} value={value}>
              {DOCUMENT_CATEGORY_LABELS[value]}
            </option>
          ))}
        </select>
        <select value={filters.status} onChange={(e) => updateFilter("status", e.target.value as DocumentStatus | "")} className={selectClass}>
          <option value="">همه وضعیت‌ها</option>
          {(Object.keys(DOCUMENT_STATUS_LABELS) as DocumentStatus[]).map((value) => (
            <option key={value} value={value}>
              {DOCUMENT_STATUS_LABELS[value]}
            </option>
          ))}
        </select>
        {filtersActive && (
          <button
            type="button"
            onClick={() => {
              setFilters(EMPTY_FILTERS);
              setSearchInput("");
              setPage(1);
            }}
            className="text-sm text-slate-600 underline"
          >
            پاک کردن فیلترها
          </button>
        )}
        <span className="ms-auto flex items-center gap-3 text-sm text-slate-500">
          {selectedIds.length > 0 && (
            <button type="button" onClick={() => setSelection({ sig: filterSig, ids: [] })} className="underline">
              لغو انتخاب
            </button>
          )}
          <button
            type="button"
            onClick={() => setBulkOpen(true)}
            disabled={count === 0}
            title="دانلود PDFهای ساخته‌شده به‌صورت فایل ZIP"
            className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40"
          >
            چاپ لیست
            <span className="ms-2 text-xs font-normal text-slate-400">({selectionLabel(selectedIds.length, filtersActive)})</span>
          </button>
          <span>{count} مستند</span>
        </span>
      </section>

      {error && <ErrorBanner message={error} />}
      {loading && rows.length === 0 && <LoadingBanner />}

      {!error && !loading && rows.length === 0 && (
        <EmptyBanner message={filtersActive ? "مستندی با این مشخصات یافت نشد." : "هنوز مستندی ثبت نشده است."} />
      )}

      {rows.length > 0 && (
        <div className={`overflow-x-auto rounded-lg border border-slate-200 bg-white ${loading ? "opacity-60" : ""}`}>
          <table className="w-full min-w-[1150px] text-right text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="w-8 px-3 py-3">
                  <input
                    type="checkbox"
                    aria-label="انتخاب همهٔ مستندات این صفحه"
                    checked={pageAllSelected}
                    onChange={togglePage}
                  />
                </th>
                {COLUMNS.map((column) => (
                  <th key={column} className="whitespace-nowrap px-3 py-3 font-medium">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={row.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-3 py-3">
                    <input
                      type="checkbox"
                      aria-label={`انتخاب ${row.full_code}`}
                      checked={selectedIds.includes(row.id)}
                      onChange={() => toggleSelected(row.id)}
                    />
                  </td>
                  <td className="px-3 py-3 text-slate-500">{(currentPage - 1) * PAGE_SIZE + index + 1}</td>
                  <td className="whitespace-nowrap px-3 py-3">{row.category_label}</td>
                  <td className="max-w-[260px] truncate px-3 py-3 font-medium text-slate-900" title={row.title}>
                    {row.title}
                  </td>
                  <td className="whitespace-nowrap px-3 py-3">{row.group_label}</td>
                  <td className="px-3 py-3">
                    <Code>{row.revision_display}</Code>
                  </td>
                  <td className="px-3 py-3">
                    <Code>{row.code}</Code>
                  </td>
                  <td className="px-3 py-3">
                    <ResponsibilityCell pair={row.responsibilities.accountant} />
                  </td>
                  <td className="px-3 py-3">
                    <ResponsibilityCell pair={row.responsibilities.questioner} />
                  </td>
                  <td className="px-3 py-3">
                    <ResponsibilityCell pair={row.responsibilities.responder} />
                  </td>
                  <td className="px-3 py-3">
                    <SignOffCell signoff={row.signoffs.creater} />
                  </td>
                  <td className="px-3 py-3">
                    <SignOffCell signoff={row.signoffs.confirmer} />
                  </td>
                  <td className="px-3 py-3">
                    <SignOffCell signoff={row.signoffs.approver} />
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusBadge status={row.status} label={row.status_label} />
                      <Link
                        href={`/documents/${row.id}/edit`}
                        className={
                          row.can_edit && canCreate && row.action === "complete"
                            ? "rounded bg-slate-900 px-3 py-1 text-xs font-medium text-white hover:bg-slate-700"
                            : "rounded border border-slate-300 bg-white px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                        }
                      >
                        {row.can_edit && canCreate
                          ? row.action === "complete"
                            ? DOCUMENT_ACTION_LABELS.complete
                            : "ویرایش"
                          : "مشاهده"}
                      </Link>
                      <WorkflowActions
                        row={row}
                        onDone={(message) => {
                          setActionError(null);
                          setNotice(message);
                          setReloadToken((n) => n + 1);
                        }}
                      />
                      <PdfActions
                        row={row}
                        status={pdfStatus[row.id] ?? row.pdf_status}
                        canPrint={canPrint}
                        previewing={previewingId === row.id}
                        onPrint={() => handlePrint(row)}
                        onRebuild={() => void runOfficialBuild(row)}
                        onPreview={() => handlePreview(row)}
                      />
                      {canCreate && row.can_revise && (
                        <button
                          type="button"
                          onClick={() => handleRevise(row)}
                          disabled={revisingId === row.id}
                          className="rounded bg-slate-900 px-3 py-1 text-xs font-medium text-white hover:bg-slate-700 disabled:opacity-50"
                        >
                          {revisingId === row.id ? "..." : "بازنگری جدید"}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {bulkOpen && (
        <BulkPrintDialog
          selection={bulkSelection}
          label={selectionLabel(selectedIds.length, filtersActive)}
          onClose={() => setBulkOpen(false)}
        />
      )}

      {totalPages > 1 && (
        <nav className="flex items-center justify-center gap-4 text-sm" aria-label="صفحه‌بندی">
          <button
            type="button"
            onClick={() => setPage(currentPage - 1)}
            disabled={currentPage <= 1}
            className="rounded border border-slate-300 bg-white px-3 py-1.5 disabled:opacity-40"
          >
            قبلی
          </button>
          <span className="text-slate-600">
            صفحه {currentPage} از {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setPage(currentPage + 1)}
            disabled={currentPage >= totalPages}
            className="rounded border border-slate-300 bg-white px-3 py-1.5 disabled:opacity-40"
          >
            بعدی
          </button>
        </nav>
      )}
    </div>
  );
}
