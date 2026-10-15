"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { ArrowRight, GitCompareArrows } from "lucide-react";
import { ApiError, apiGet } from "@/lib/api-client";
import { changeCount, diffContents, type Block, type DiffRow, type Token } from "@/lib/diff";
import type { ContentResponse } from "@/lib/types";
import { Code } from "@/components/Code";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
import { StatusBadge } from "@/components/StatusBadge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { Switch } from "@/components/ui/Switch";
import { cx } from "@/components/ui/cx";

const KIND_LABELS: Record<DiffRow["kind"], string> = {
  same: "بدون تغییر",
  changed: "تغییر کرده",
  added: "افزوده شده",
  removed: "حذف شده",
};

const KIND_TONE: Record<DiffRow["kind"], string> = {
  same: "bg-muted text-muted-foreground",
  changed: "bg-amber-50 text-amber-800 ring-1 ring-inset ring-amber-600/20 dark:bg-amber-950/40 dark:text-amber-200",
  added: "bg-emerald-50 text-emerald-800 ring-1 ring-inset ring-emerald-600/20 dark:bg-emerald-950/40 dark:text-emerald-200",
  removed: "bg-rose-50 text-rose-800 ring-1 ring-inset ring-rose-600/20 dark:bg-rose-950/40 dark:text-rose-200",
};

function useContent(id: number | null) {
  const [state, setState] = useState<{ id: number; data: ContentResponse | null; error: string | null } | null>(null);
  useEffect(() => {
    if (id === null) return;
    let cancelled = false;
    apiGet<ContentResponse>(`/documents/${id}/content/`)
      .then((data) => !cancelled && setState({ id, data, error: null }))
      .catch((err) => !cancelled && setState({ id, data: null, error: err instanceof ApiError ? err.message : "دریافت مستند ممکن نشد." }));
    return () => {
      cancelled = true;
    };
  }, [id]);
  return state && state.id === id ? state : null;
}

/** «مقایسه با بازنگری قبلی» (Phase 21): this revision beside the one it replaced (or `?with=` another),
 *  block by block, with the changed words marked. The newer revision is on the right, as it reads first. */
export function CompareScreen() {
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const current = useContent(Number(id));
  const withParam = Number(search.get("with")) || null;
  const otherId = withParam ?? current?.data?.document.previous_revision_id ?? null;
  const other = useContent(otherId);
  const [changesOnly, setChangesOnly] = useState(true);

  const pair = useMemo(() => {
    if (!current?.data || !other?.data) return null;
    // Whichever is the later revision is "new"; `?with=` may point either way.
    const [older, newer] =
      other.data.document.revision <= current.data.document.revision ? [other.data, current.data] : [current.data, other.data];
    return { older, newer, rows: diffContents(older, newer) };
  }, [current, other]);

  if (current?.error) return <ErrorBanner message={current.error} />;
  if (!current?.data) return <LoadingBanner />;
  const document = current.data.document;

  const back = (
    <Link href={`/documents/${document.id}/edit`} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
      <ArrowRight className="size-4" />
      بازگشت به مستند
    </Link>
  );

  if (otherId === null) {
    return (
      <div className="mx-auto max-w-5xl space-y-6">
        {back}
        <EmptyState icon={<GitCompareArrows />} message="این نخستین بازنگری مستند است؛ بازنگری قبلی برای مقایسه وجود ندارد." />
      </div>
    );
  }
  if (other?.error) return <ErrorBanner message={other.error} />;
  if (!pair) return <LoadingBanner />;

  const changes = changeCount(pair.rows);
  const rows = changesOnly ? pair.rows.filter((row) => row.kind !== "same") : pair.rows;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      {back}
      <PageHeader title="مقایسهٔ بازنگری‌ها" subtitle={document.title} />

      <Card className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted-foreground">جدیدتر:</span>
          <Code>{pair.newer.document.full_code}</Code>
          <StatusBadge status={pair.newer.document.status} label={pair.newer.document.status_label} />
          <span className="mx-1 text-subtle-foreground">←</span>
          <span className="text-muted-foreground">قبلی:</span>
          <Code>{pair.older.document.full_code}</Code>
          <StatusBadge status={pair.older.document.status} label={pair.older.document.status_label} />
        </div>
        <label className="flex items-center gap-2 text-sm text-soft-foreground">
          <Switch checked={changesOnly} onChange={(event) => setChangesOnly(event.target.checked)} aria-label="فقط تغییرات" />
          فقط تغییرات ({changes.toLocaleString("fa-IR")})
        </label>
      </Card>

      {pair.newer.body_kind !== pair.older.body_kind && (
        <p className="text-sm text-muted-foreground">نوع بدنهٔ دو بازنگری فرق دارد؛ مقایسه بند به بند است.</p>
      )}

      {rows.length === 0 ? (
        <EmptyState icon={<GitCompareArrows />} message="محتوای دو بازنگری یکسان است." />
      ) : (
        <ol className="space-y-4">
          {rows.map((row, index) => (
            <li key={index}>
              <Card className="p-0">
                <div className="flex items-center gap-2 border-b border-border px-4 py-2.5 text-sm">
                  <span className="font-bold text-foreground">{row.label}</span>
                  <span className={cx("rounded-full px-2 py-0.5 text-xs", KIND_TONE[row.kind])}>{KIND_LABELS[row.kind]}</span>
                </div>
                <div className="grid divide-y divide-border md:grid-cols-2 md:divide-x md:divide-y-0 md:divide-x-reverse">
                  <Side title={`بازنگری ${pair.newer.document.revision_display}`}>
                    {row.kind === "removed" ? <Missing /> : row.kind === "changed" ? <Tokens tokens={row.newTokens} /> : <Lines block={row.new} />}
                  </Side>
                  <Side title={`بازنگری ${pair.older.document.revision_display}`}>
                    {row.kind === "added" ? <Missing /> : row.kind === "changed" ? <Tokens tokens={row.oldTokens} /> : <Lines block={row.old} />}
                  </Side>
                </div>
              </Card>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function Side({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0 px-4 py-3">
      <p className="mb-1.5 text-[11px] text-muted-foreground">{title}</p>
      <div className="whitespace-pre-wrap break-words text-sm leading-7 text-foreground">{children}</div>
    </div>
  );
}

function Lines({ block }: { block: Block }) {
  return block.lines.length ? <>{block.lines.join("\n")}</> : <span className="text-subtle-foreground">(خالی)</span>;
}

function Missing() {
  return <span className="text-subtle-foreground">—</span>;
}

function Tokens({ tokens }: { tokens: Token[] }) {
  return (
    <>
      {tokens.map((token, index) =>
        token.op === "same" ? (
          <span key={index}>{token.text}</span>
        ) : token.op === "add" ? (
          <ins key={index} className="rounded bg-emerald-100 px-0.5 text-emerald-900 no-underline dark:bg-emerald-900/50 dark:text-emerald-100">
            {token.text}
          </ins>
        ) : (
          <del key={index} className="rounded bg-rose-100 px-0.5 text-rose-900 dark:bg-rose-900/50 dark:text-rose-100">
            {token.text}
          </del>
        ),
      )}
    </>
  );
}
