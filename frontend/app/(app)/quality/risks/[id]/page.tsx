"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AlarmClock, ArrowRight, Building2, CalendarClock, Gauge, Pencil, UserRound, UserX } from "lucide-react";
import { Code } from "@/components/Code";
import { RiskActivityFeed } from "@/components/quality/NcActivityFeed";
import { RiskLevelBadge, RiskStatusBadge } from "@/components/quality/Badges";
import { RiskFormDialog } from "@/components/quality/RiskFormDialog";
import { TextBlock } from "@/components/quality/TextBlock";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
import { Button } from "@/components/ui/Button";
import { Card, cardClass } from "@/components/ui/Card";
import { cx } from "@/components/ui/cx";
import { formatJalali, toPersianDigits } from "@/lib/jalali";
import { IMPACT_LABELS, LIKELIHOOD_LABELS, assessmentText, type RiskItem } from "@/lib/quality";
import { useApiQuery } from "@/lib/use-api-query";

/** «جزئیات ریسک» (Phase 18): the risk, its assessment, who watches it and what is being done, and its
 *  history. «ویرایش» (which also moves the status) is offered only when the server says `can_edit`. */
export default function RiskPage() {
  const { id } = useParams<{ id: string }>();
  const riskId = Number(id);
  const [reload, setReload] = useState(0);
  const record = useApiQuery<RiskItem>(`/quality/risks/${riskId}/`, reload);
  const [editing, setEditing] = useState(false);

  if (record.loading) return <LoadingBanner />;
  if (record.error || !record.data) return <ErrorBanner message={record.error ?? "دریافت ریسک ممکن نشد."} />;
  const risk = record.data;

  const tiles: [string, string, React.ReactNode, string?][] = [
    ["گرهٔ مربوط", risk.owner_node_name, <Building2 key="n" />],
    [
      "مسئول پیگیری",
      risk.owner_name ? (risk.owner_is_active === false ? `${risk.owner_name} (غیرفعال)` : risk.owner_name) : "بدون مسئول",
      risk.owner_is_active === false ? <UserX key="u" className="text-amber-600" /> : <UserRound key="u" />,
    ],
    ["احتمال × اثر", assessmentText(risk.likelihood, risk.impact), <Gauge key="s" />],
    [
      "تاریخ بازنگری",
      risk.review_on ? formatJalali(risk.review_on) : "تعیین نشده",
      risk.review_overdue ? <AlarmClock key="r" /> : <CalendarClock key="r" />,
      risk.review_overdue ? "text-rose-700" : undefined,
    ],
  ];

  return (
    <div className="space-y-6">
      <nav className="text-sm">
        <Link href="/quality/risks" className="group inline-flex items-center gap-1.5 text-slate-500 transition-colors hover:text-slate-900">
          <ArrowRight className="size-4 transition-transform duration-200 group-hover:translate-x-0.5" />
          ریسک‌ها
        </Link>
      </nav>

      <header className={cx(cardClass, "relative overflow-hidden p-5 sm:p-6")}>
        <div aria-hidden className="absolute inset-x-0 top-0 h-1 bg-gradient-to-l from-brand-500 via-indigo-400 to-emerald-400 opacity-80" />
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <Code>{risk.code}</Code>
              <RiskLevelBadge level={risk.level} label={risk.level_label} score={toPersianDigits(risk.score)} />
              <RiskStatusBadge status={risk.status} label={risk.status_label} />
            </div>
            <h1 className="text-2xl font-bold leading-10 text-slate-900">{risk.title}</h1>
          </div>
          {risk.can_edit && (
            <Button size="sm" icon={<Pencil />} onClick={() => setEditing(true)}>
              ویرایش
            </Button>
          )}
        </div>

        <dl className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {tiles.map(([label, value, icon, tone]) => (
            <div key={label} className="flex items-center gap-3 rounded-xl bg-slate-50 px-3 py-2.5 ring-1 ring-inset ring-slate-200/70">
              <span className={cx("text-slate-400 [&_svg]:size-4", tone)}>{icon}</span>
              <div className="min-w-0">
                <dt className="text-xs text-slate-500">{label}</dt>
                <dd className={cx("truncate text-sm font-bold text-slate-800", tone)}>{value}</dd>
              </div>
            </div>
          ))}
        </dl>
        <p className="mt-3 text-xs text-slate-500">
          احتمال: {LIKELIHOOD_LABELS[risk.likelihood]} · اثر: {IMPACT_LABELS[risk.impact]} · ثبت توسط {risk.created_by_name}
        </p>
        {risk.review_overdue && <p className="mt-2 text-xs font-bold text-rose-700">زمان بازنگری این ریسک گذشته است.</p>}
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <Card aria-label="شرح ریسک" className="self-start">
          <div className="space-y-3">
            <TextBlock title="شرح" text={risk.description} />
            <TextBlock title="برنامهٔ کاهش" text={risk.mitigation_plan} tone="success" />
            {!risk.mitigation_plan && <p className="text-sm text-slate-500">هنوز برنامه‌ای برای کاهش این ریسک نوشته نشده است.</p>}
          </div>
        </Card>
        <aside>
          <RiskActivityFeed riskId={riskId} version={reload} />
        </aside>
      </div>

      {editing && (
        <RiskFormDialog
          risk={risk}
          onSaved={() => {
            setEditing(false);
            setReload((n) => n + 1);
          }}
          onClose={() => setEditing(false)}
        />
      )}
    </div>
  );
}
