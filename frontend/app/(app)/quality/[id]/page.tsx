"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { apiPost } from "@/lib/api-client";
import { formatJalali } from "@/lib/jalali";
import type { NcSeverity, NonConformance } from "@/lib/quality";
import { useApiQuery } from "@/lib/use-api-query";
import { Code } from "@/components/Code";
import { AcceptDialog } from "@/components/quality/AcceptDialog";
import { ActionsPanel } from "@/components/quality/ActionsPanel";
import { NcStatusBadge, SeverityBadge } from "@/components/quality/Badges";
import { NcActivityFeed } from "@/components/quality/NcActivityFeed";
import { NcFormDialog } from "@/components/quality/NcFormDialog";
import { TextDialog } from "@/components/quality/TextDialog";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
import { ArrowRight, Building2, CalendarSearch, CheckCheck, FileText, Pencil, RotateCcw, ShieldAlert, UserRound, XCircle } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card, cardClass } from "@/components/ui/Card";
import { cx } from "@/components/ui/cx";

type Dialog = "edit" | "accept" | "reject" | "reopen" | null;

/** One labelled paragraph of the record — shown only when there is something to say. */
function TextBlock({ title, text, tone = "plain" }: { title: string; text: string; tone?: "plain" | "danger" | "success" }) {
  if (!text) return null;
  const surface =
    tone === "danger" ? "bg-rose-50/70 ring-rose-200" : tone === "success" ? "bg-emerald-50/70 ring-emerald-200" : "bg-slate-50 ring-slate-200/70";
  return (
    <section className={cx("rounded-xl px-4 py-3 ring-1 ring-inset", surface)}>
      <h3 className="mb-1 text-xs font-bold text-slate-600">{title}</h3>
      <p className="whitespace-pre-line text-sm leading-7 text-slate-800">{text}</p>
    </section>
  );
}

/** «جزئیات عدم‌انطباق» (Phase 18): the record, the buttons the server says the viewer may press, and its
 *  history. Every button here is a request the server accepts — `can_*` are the very functions it enforces. */
export default function NonConformancePage() {
  const { id } = useParams<{ id: string }>();
  const ncId = Number(id);
  const [reload, setReload] = useState(0);
  const record = useApiQuery<NonConformance>(`/quality/nonconformances/${ncId}/`, reload);
  const [dialog, setDialog] = useState<Dialog>(null);

  if (record.loading) return <LoadingBanner />;
  if (record.error || !record.data) return <ErrorBanner message={record.error ?? "دریافت عدم‌انطباق ممکن نشد."} />;
  const nc = record.data;

  const refresh = () => {
    setDialog(null);
    setReload((n) => n + 1);
  };

  async function transition(action: "reject" | "reopen", reason: string) {
    await apiPost(`/quality/nonconformances/${ncId}/${action}/`, { reason });
    refresh();
  }

  async function accept(rootCause: string, severity: NcSeverity) {
    await apiPost(`/quality/nonconformances/${ncId}/accept/`, { root_cause: rootCause, severity });
    refresh();
  }

  return (
    <div className="space-y-6">
      <nav className="text-sm">
        <Link href="/quality" className="group inline-flex items-center gap-1.5 text-slate-500 transition-colors hover:text-slate-900">
          <ArrowRight className="size-4 transition-transform duration-200 group-hover:translate-x-0.5" />
          عدم‌انطباق‌ها
        </Link>
      </nav>

      <header className={cx(cardClass, "relative overflow-hidden p-5 sm:p-6")}>
        <div aria-hidden className="absolute inset-x-0 top-0 h-1 bg-gradient-to-l from-brand-500 via-indigo-400 to-emerald-400 opacity-80" />
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <Code>{nc.code}</Code>
              <SeverityBadge severity={nc.severity} label={nc.severity_label} />
              <NcStatusBadge status={nc.status} label={nc.status_label} />
            </div>
            <h1 className="text-2xl font-bold leading-10 text-slate-900">{nc.title}</h1>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            {nc.can_triage && (
              <>
                <Button variant="primary" size="sm" icon={<CheckCheck />} onClick={() => setDialog("accept")}>
                  پذیرش و ریشه‌یابی
                </Button>
                <Button size="sm" icon={<XCircle />} onClick={() => setDialog("reject")}>
                  رد
                </Button>
              </>
            )}
            {nc.can_reopen && (
              <Button size="sm" icon={<RotateCcw />} onClick={() => setDialog("reopen")}>
                بازگشایی
              </Button>
            )}
            {nc.can_edit && (
              <Button size="sm" icon={<Pencil />} onClick={() => setDialog("edit")}>
                ویرایش
              </Button>
            )}
          </div>
        </div>

        <dl className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {(
            [
              ["گرهٔ مربوط", nc.owner_node_name, <Building2 key="n" />],
              ["ثبت‌کننده", nc.reported_by_name, <UserRound key="u" />],
              ["تاریخ کشف", formatJalali(nc.detected_on), <CalendarSearch key="d" />],
              ["منبع", nc.source_label, <ShieldAlert key="s" />],
            ] as const
          ).map(([label, value, icon]) => (
            <div key={label} className="flex items-center gap-3 rounded-xl bg-slate-50 px-3 py-2.5 ring-1 ring-inset ring-slate-200/70">
              <span className="text-slate-400 [&_svg]:size-4">{icon}</span>
              <div className="min-w-0">
                <dt className="text-xs text-slate-500">{label}</dt>
                <dd className="truncate text-sm font-bold text-slate-800">{value}</dd>
              </div>
            </div>
          ))}
        </dl>

        {nc.related_document && nc.related_document_code && (
          <p className="mt-4 flex flex-wrap items-center gap-2 text-sm text-slate-600">
            <FileText className="size-4 text-slate-400" />
            مستند مرتبط:
            <Link href={`/documents/${nc.related_document}/edit`} className="inline-flex items-center gap-2 hover:text-brand-700">
              <Code>{nc.related_document_code}</Code>
              <span>{nc.related_document_title}</span>
            </Link>
          </p>
        )}
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-6">
          <Card aria-label="شرح">
            <div className="space-y-3">
              <TextBlock title="شرح مشکل" text={nc.description} />
              <TextBlock title="ریشهٔ مشکل" text={nc.root_cause} />
              <TextBlock title="دلیل رد" text={nc.rejection_reason} tone="danger" />
              <TextBlock title="اثربخشی اقدام‌ها" text={nc.effectiveness_note} tone="success" />
            </div>
          </Card>

          <ActionsPanel nc={nc} version={reload} onChanged={refresh} />
        </div>
        <aside>
          <NcActivityFeed ncId={ncId} version={reload} />
        </aside>
      </div>

      {dialog === "edit" && (
        <NcFormDialog
          nc={nc}
          onSaved={() => refresh()}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog === "accept" && <AcceptDialog severity={nc.severity} onSubmit={accept} onCancel={() => setDialog(null)} />}
      {dialog === "reject" && (
        <TextDialog
          title="رد عدم‌انطباق"
          description="این مورد عدم‌انطباق واقعی نیست. دلیل شما روی پروندهٔ مورد می‌ماند و ثبت‌کننده از آن باخبر می‌شود."
          fieldLabel="دلیل رد"
          confirmLabel="رد"
          danger
          onSubmit={(reason) => transition("reject", reason)}
          onCancel={() => setDialog(null)}
        />
      )}
      {dialog === "reopen" && (
        <TextDialog
          title="بازگشایی عدم‌انطباق"
          description={
            nc.status === "REJECTED"
              ? "مورد رد‌شده به مرحلهٔ بررسی برمی‌گردد."
              : "مورد بسته‌شده دوباره «در دست اقدام» می‌شود؛ اقدام‌های تاییدشده همان‌طور می‌مانند."
          }
          fieldLabel="دلیل بازگشایی"
          confirmLabel="بازگشایی"
          onSubmit={(reason) => transition("reopen", reason)}
          onCancel={() => setDialog(null)}
        />
      )}
    </div>
  );
}
