"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  AlarmClock,
  ArrowRight,
  Building2,
  CalendarClock,
  CalendarRange,
  CheckCheck,
  Pencil,
  Play,
  UserCog,
  UserRound,
  UserX,
  XCircle,
} from "lucide-react";
import { Code } from "@/components/Code";
import { AuditActivityFeed } from "@/components/quality/NcActivityFeed";
import { AuditFormDialog } from "@/components/quality/AuditFormDialog";
import { AuditStatusBadge } from "@/components/quality/Badges";
import { ChangeAuditorDialog } from "@/components/quality/ChangeAuditorDialog";
import { FindingsPanel } from "@/components/quality/FindingsPanel";
import { TextBlock } from "@/components/quality/TextBlock";
import { TextDialog } from "@/components/quality/TextDialog";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
import { Button } from "@/components/ui/Button";
import { Card, cardClass } from "@/components/ui/Card";
import { cx } from "@/components/ui/cx";
import { ApiError, apiPost } from "@/lib/api-client";
import { formatJalali, todayIso } from "@/lib/jalali";
import { auditIsLate, type InternalAudit } from "@/lib/quality";
import { useApiQuery } from "@/lib/use-api-query";

type Dialog = "edit" | "auditor" | "complete" | "cancel" | null;

/** «جزئیات ممیزی» (Phase 18): the audit, the buttons the server says the viewer may press, the findings it
 *  raised and its history. Every button is a request the server accepts — `can_*` are the very functions
 *  it enforces. */
export default function AuditPage() {
  const { id } = useParams<{ id: string }>();
  const auditId = Number(id);
  const today = useMemo(() => todayIso(), []);
  const [reload, setReload] = useState(0);
  const record = useApiQuery<InternalAudit>(`/quality/audits/${auditId}/`, reload);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (record.loading) return <LoadingBanner />;
  if (record.error || !record.data) return <ErrorBanner message={record.error ?? "دریافت ممیزی ممکن نشد."} />;
  const audit = record.data;

  const refresh = () => {
    setDialog(null);
    setError(null);
    setReload((n) => n + 1);
  };

  async function start() {
    setStarting(true);
    setError(null);
    try {
      await apiPost(`/quality/audits/${auditId}/start/`);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "آغاز ممیزی ممکن نشد.");
    } finally {
      setStarting(false);
    }
  }

  const decide = (action: "complete" | "cancel") => async (text: string) => {
    await apiPost(`/quality/audits/${auditId}/${action}/`, action === "complete" ? { summary: text } : { reason: text });
    refresh();
  };

  const late = auditIsLate(audit, today);
  const when: [string, string] = audit.completed_at
    ? ["تاریخ انجام", formatJalali(audit.completed_at)]
    : audit.started_at
      ? ["تاریخ آغاز", formatJalali(audit.started_at)]
      : ["تاریخ ثبت", formatJalali(audit.created_at)];

  return (
    <div className="space-y-6">
      <nav className="text-sm">
        <Link href="/quality/audits" className="group inline-flex items-center gap-1.5 text-slate-500 transition-colors hover:text-slate-900">
          <ArrowRight className="size-4 transition-transform duration-200 group-hover:translate-x-0.5" />
          ممیزی‌ها
        </Link>
      </nav>

      <header className={cx(cardClass, "relative overflow-hidden p-5 sm:p-6")}>
        <div aria-hidden className="absolute inset-x-0 top-0 h-1 bg-gradient-to-l from-brand-500 via-indigo-400 to-emerald-400 opacity-80" />
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <Code>{audit.code}</Code>
              <AuditStatusBadge status={audit.status} label={audit.status_label} />
              {late && (
                <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-xs text-rose-800 ring-1 ring-inset ring-rose-600/20">
                  <AlarmClock className="size-3.5" />
                  از تاریخ برنامه گذشته
                </span>
              )}
            </div>
            <h1 className="text-2xl font-bold leading-10 text-slate-900">{audit.title}</h1>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            {audit.can_start && (
              <Button variant="primary" size="sm" icon={<Play />} onClick={start} loading={starting}>
                آغاز ممیزی
              </Button>
            )}
            {audit.can_complete && (
              <Button variant="primary" size="sm" icon={<CheckCheck />} onClick={() => setDialog("complete")}>
                تکمیل ممیزی
              </Button>
            )}
            {audit.can_edit && (
              <Button size="sm" icon={<Pencil />} onClick={() => setDialog("edit")}>
                ویرایش
              </Button>
            )}
            {!audit.can_edit && audit.can_change_auditor && (
              <Button size="sm" icon={<UserCog />} onClick={() => setDialog("auditor")}>
                تغییر ممیز
              </Button>
            )}
            {audit.can_cancel && (
              <Button size="sm" variant="danger" icon={<XCircle />} onClick={() => setDialog("cancel")}>
                لغو ممیزی
              </Button>
            )}
          </div>
        </div>

        <dl className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {(
            [
              ["گرهٔ ممیزی‌شونده", audit.scope_node_name, <Building2 key="n" />],
              [
                "ممیز اصلی",
                audit.lead_auditor_is_active ? audit.lead_auditor_name : `${audit.lead_auditor_name} (غیرفعال)`,
                audit.lead_auditor_is_active ? <UserRound key="u" /> : <UserX key="u" className="text-amber-600" />,
              ],
              ["تاریخ برنامه", formatJalali(audit.planned_on), <CalendarClock key="p" />],
              [when[0], when[1], <CalendarRange key="w" />],
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
        {!audit.lead_auditor_is_active && audit.can_change_auditor && (
          <p className="mt-3 text-xs text-amber-700">ممیز اصلی غیرفعال شده است؛ ممیز دیگری را جایگزین کنید.</p>
        )}
        {error && (
          <div className="mt-4">
            <ErrorBanner message={error} />
          </div>
        )}
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-6">
          {(audit.summary || audit.cancel_reason) && (
            <Card aria-label="نتیجه">
              <div className="space-y-3">
                <TextBlock title="خلاصهٔ ممیزی" text={audit.summary} tone="success" />
                <TextBlock title="دلیل لغو" text={audit.cancel_reason} tone="danger" />
              </div>
            </Card>
          )}
          <FindingsPanel audit={audit} version={reload} onChanged={() => setReload((n) => n + 1)} />
        </div>
        <aside>
          <AuditActivityFeed auditId={auditId} version={reload} />
        </aside>
      </div>

      {dialog === "edit" && <AuditFormDialog audit={audit} onSaved={() => refresh()} onClose={() => setDialog(null)} />}
      {dialog === "auditor" && <ChangeAuditorDialog audit={audit} onSaved={refresh} onClose={() => setDialog(null)} />}
      {dialog === "complete" && (
        <TextDialog
          title="تکمیل ممیزی"
          description="چه چیزی بررسی شد و چه یافته شد؟ حتی اگر یافته‌ای نبود، همین را بنویسید. پس از تکمیل، ممیزی تغییر نمی‌کند."
          fieldLabel="خلاصهٔ ممیزی"
          confirmLabel="تکمیل ممیزی"
          onSubmit={decide("complete")}
          onCancel={() => setDialog(null)}
        />
      )}
      {dialog === "cancel" && (
        <TextDialog
          title="لغو ممیزی"
          description="ممیز اصلی از لغو باخبر می‌شود. یافته‌هایی که تا اینجا ثبت شده‌اند می‌مانند و مسیر خودشان را ادامه می‌دهند."
          fieldLabel="دلیل لغو"
          confirmLabel="لغو ممیزی"
          danger
          onSubmit={decide("cancel")}
          onCancel={() => setDialog(null)}
        />
      )}
    </div>
  );
}
