"use client";

import { useState } from "react";
import { CalendarDays, CheckCheck, Plus, Undo2, XCircle } from "lucide-react";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { LeaveFormDialog } from "@/components/leave/LeaveFormDialog";
import { Pager } from "@/components/Pager";
import { TextDialog } from "@/components/quality/TextDialog";
import { ErrorBanner } from "@/components/StatusBanner";
import { Avatar } from "@/components/ui/Avatar";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { selectClass } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { Tabs } from "@/components/ui/Tabs";
import { apiPost } from "@/lib/api-client";
import { useCurrentUser } from "@/lib/current-user";
import { formatJalali } from "@/lib/jalali";
import {
  LEAVE_STATUS_LABELS,
  LEAVE_STATUS_TONE,
  daysText,
  leaveQueryParams,
  leaveTabs,
  type LeaveRequest,
  type LeaveStatus,
  type LeaveTab,
} from "@/lib/leave";
import { usePagedQuery } from "@/lib/use-paged-query";

const PAGE_SIZE = 20;
const TAB_LABELS: Record<LeaveTab, string> = { mine: "مرخصی‌های من", decide: "منتظر تصمیم من", all: "همهٔ درخواست‌ها" };

type Dialog = { kind: "new" } | { kind: "approve" | "reject" | "cancel"; leave: LeaveRequest } | null;

/** «مرخصی» (Phase 19): ask for days off and follow the answer; a مسئول (or the مدیر عامل) decides the
 *  requests of the people under them; HR reads every request. Each button is one the server says this
 *  person may press (`can_decide`, `can_cancel`). */
export default function LeavePage() {
  const { user, can } = useCurrentUser();
  const top = user?.access_roll === "EMPLOYER" && user?.access_level === "L1";
  const tabs = leaveTabs({ leads: Boolean(user?.memberships?.some((m) => m.is_lead)), top, hr: can("manage_personnel") });
  const [tab, setTab] = useState<LeaveTab>("mine");
  const [status, setStatus] = useState<LeaveStatus | "">("");
  const [page, setPage] = useState(1);
  const [reload, setReload] = useState(0);
  const [dialog, setDialog] = useState<Dialog>(null);

  const { rows, count, error, loading } = usePagedQuery<LeaveRequest>(
    "/leave/requests/",
    leaveQueryParams(tabs.includes(tab) ? tab : "mine", status, page, PAGE_SIZE),
    reload,
  );
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));
  const done = () => {
    setDialog(null);
    setReload((n) => n + 1);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="مرخصی"
        subtitle="درخواست مرخصی، و تصمیم دربارهٔ درخواست‌های کسانی که مسئول آن‌ها هستید"
        actions={
          <Button variant="primary" icon={<Plus />} onClick={() => setDialog({ kind: "new" })}>
            درخواست مرخصی
          </Button>
        }
      />

      <Card as="section" className="space-y-3 p-3 sm:p-4">
        {tabs.length > 1 && (
          <Tabs
            label="نمای مرخصی‌ها"
            items={tabs.map((id) => ({ id, label: TAB_LABELS[id] }))}
            value={tab}
            onChange={(next) => {
              setTab(next);
              setPage(1);
            }}
          />
        )}
        <select
          aria-label="وضعیت"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value as LeaveStatus | "");
            setPage(1);
          }}
          className={`${selectClass} w-full sm:w-56`}
        >
          <option value="">همهٔ وضعیت‌ها</option>
          {(Object.keys(LEAVE_STATUS_LABELS) as LeaveStatus[]).map((value) => (
            <option key={value} value={value}>
              {LEAVE_STATUS_LABELS[value]}
            </option>
          ))}
        </select>
      </Card>

      {loading ? (
        <Card flush role="status" aria-label="در حال بارگذاری">
          {[0, 1, 2].map((i) => (
            <div key={i} className="space-y-2.5 border-b border-slate-100 px-5 py-4 last:border-0">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-3 w-1/3" />
            </div>
          ))}
        </Card>
      ) : error ? (
        <ErrorBanner message={error} />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={<CalendarDays />}
          message={tab === "decide" ? "درخواستی منتظر تصمیم شما نیست." : tab === "mine" ? "هنوز درخواست مرخصی ثبت نکرده‌اید." : "درخواستی پیدا نشد."}
        />
      ) : (
        <Card flush>
          <ul className="divide-y divide-slate-100">
            {rows.map((leave) => (
              <LeaveRow key={leave.id} leave={leave} showRequester={tab !== "mine"} onAct={(kind) => setDialog({ kind, leave })} />
            ))}
          </ul>
        </Card>
      )}

      <Pager page={page} totalPages={totalPages} onChange={setPage} />

      {dialog?.kind === "new" && <LeaveFormDialog onSaved={done} onClose={() => setDialog(null)} />}
      {dialog?.kind === "approve" && (
        <TextDialog
          title="تایید مرخصی"
          description={`${dialog.leave.requester_name} — ${dialog.leave.leave_type_label}، ${daysText(dialog.leave.days)}`}
          fieldLabel="یادداشت (اختیاری)"
          confirmLabel="تایید"
          required={false}
          onSubmit={async (note) => {
            await apiPost(`/leave/requests/${dialog.leave.id}/approve/`, { note });
            done();
          }}
          onCancel={() => setDialog(null)}
        />
      )}
      {dialog?.kind === "reject" && (
        <TextDialog
          title="رد درخواست مرخصی"
          description="دلیل شما برای درخواست‌دهنده نمایش داده می‌شود."
          fieldLabel="دلیل رد"
          confirmLabel="رد درخواست"
          danger
          onSubmit={async (note) => {
            await apiPost(`/leave/requests/${dialog.leave.id}/reject/`, { note });
            done();
          }}
          onCancel={() => setDialog(null)}
        />
      )}
      {dialog?.kind === "cancel" && (
        <ConfirmDialog
          title="لغو درخواست مرخصی"
          message={
            dialog.leave.status === "APPROVED"
              ? "این مرخصی تایید شده است؛ با لغو آن، کسی که تاییدش کرده باخبر می‌شود."
              : "درخواست لغو می‌شود و دیگر منتظر تصمیم نمی‌ماند."
          }
          confirmLabel="لغو درخواست"
          danger
          onConfirm={async () => {
            await apiPost(`/leave/requests/${dialog.leave.id}/cancel/`);
            done();
          }}
          onCancel={() => setDialog(null)}
        />
      )}
    </div>
  );
}

function LeaveRow({ leave, showRequester, onAct }: { leave: LeaveRequest; showRequester: boolean; onAct: (kind: "approve" | "reject" | "cancel") => void }) {
  return (
    <li className="space-y-2 px-4 py-3.5 sm:px-5">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        {showRequester && (
          <span className="inline-flex items-center gap-2 font-bold text-slate-900">
            <Avatar name={leave.requester_name} size="sm" />
            {leave.requester_name}
          </span>
        )}
        <span className="font-bold text-slate-800">
          {leave.leave_type_label} · {daysText(leave.days)}
        </span>
        <span className="text-sm text-slate-600">
          {formatJalali(leave.starts_on)}
          {leave.ends_on !== leave.starts_on && <> تا {formatJalali(leave.ends_on)}</>}
        </span>
        <Badge tone={LEAVE_STATUS_TONE[leave.status]} dot>
          {leave.status_label}
        </Badge>
      </div>
      {(showRequester && leave.node_name) || leave.reason ? (
        <p className="text-sm leading-7 text-slate-600">
          {showRequester && leave.node_name && <span className="text-slate-500">{leave.node_name}</span>}
          {showRequester && leave.node_name && leave.reason && " · "}
          {leave.reason}
        </p>
      ) : null}
      {leave.decided_by_name && (
        <p className={leave.status === "REJECTED" ? "rounded-lg bg-rose-50 px-3 py-1.5 text-xs text-rose-800" : "text-xs text-slate-500"}>
          {leave.status === "REJECTED" ? "رد توسط" : "تصمیم توسط"} {leave.decided_by_name}
          {leave.decided_at && ` · ${formatJalali(leave.decided_at)}`}
          {leave.decision_note && `: ${leave.decision_note}`}
        </p>
      )}
      {(leave.can_decide || leave.can_cancel) && (
        <div className="flex flex-wrap gap-2 pt-1">
          {leave.can_decide && (
            <>
              <Button size="sm" variant="primary" icon={<CheckCheck />} onClick={() => onAct("approve")}>
                تایید
              </Button>
              <Button size="sm" icon={<XCircle />} onClick={() => onAct("reject")}>
                رد
              </Button>
            </>
          )}
          {leave.can_cancel && (
            <Button size="sm" variant="ghost" icon={<Undo2 />} onClick={() => onAct("cancel")}>
              لغو درخواست
            </Button>
          )}
        </div>
      )}
    </li>
  );
}
