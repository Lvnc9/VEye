"use client";

import { useState } from "react";
import { ApiError, apiPatch, apiPost } from "@/lib/api-client";
import { formatJalali, toPersianDigits } from "@/lib/jalali";
import {
  ACTION_STATUS_TONE,
  actionsProgress,
  actionsSummary,
  closeHint,
  statusButtons,
  type ActionStatus,
  type CorrectiveAction,
  type NonConformance,
} from "@/lib/quality";
import { useApiQuery } from "@/lib/use-api-query";
import { ActionFormDialog } from "@/components/quality/ActionFormDialog";
import { TextDialog } from "@/components/quality/TextDialog";
import { ErrorBanner } from "@/components/StatusBanner";
import { Alert } from "@/components/ui/Alert";
import { Avatar } from "@/components/ui/Avatar";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { SkeletonLines } from "@/components/ui/Skeleton";
import { cx } from "@/components/ui/cx";
import { AlarmClock, BadgeCheck, CalendarClock, CircleSlash, ListChecks, Lock, Pencil, Plus, ShieldX, UserX } from "lucide-react";

type Dialog =
  | { kind: "add" }
  | { kind: "close" }
  | { kind: "edit" | "verify" | "fail" | "cancel"; action: CorrectiveAction }
  | null;

/**
 * «اقدام‌های اصلاحی»: the fixes for a record — who does what by when, whether it was checked — and the
 * button that closes the record once all of them are verified. Every button is one the server says the
 * viewer may press (`can_*` are the very functions the endpoints enforce); a refusal that still happens
 * (two people acting at once) shows the server's own Persian message.
 */
export function ActionsPanel({
  nc,
  version,
  onChanged,
}: {
  nc: NonConformance;
  /** Bumped by the page after any change, so the list refetches with the record. */
  version: number;
  onChanged: () => void;
}) {
  const actions = useApiQuery<CorrectiveAction[]>(`/quality/nonconformances/${nc.id}/actions/`, version);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const rows = actions.data ?? [];
  const hint = closeHint(nc);
  const base = `/quality/nonconformances/${nc.id}`;

  function done() {
    setDialog(null);
    setError(null);
    onChanged();
  }

  async function move(action: CorrectiveAction, status: ActionStatus) {
    setBusyId(action.id);
    setError(null);
    try {
      await apiPatch(`${base}/actions/${action.id}/`, { status });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تغییر وضعیت ممکن نشد.");
    } finally {
      setBusyId(null);
    }
  }

  const post = (path: string, body: object) => async () => {
    await apiPost(`${base}/${path}`, body);
    done();
  };

  return (
    <Card aria-label="اقدام‌های اصلاحی">
      <CardHeader
        title="اقدام‌های اصلاحی"
        icon={<ListChecks />}
        actions={
          <div className="flex flex-wrap gap-2">
            {nc.can_add_action && (
              <Button size="sm" icon={<Plus />} onClick={() => setDialog({ kind: "add" })}>
                افزودن اقدام
              </Button>
            )}
            {nc.can_close && (
              <Button size="sm" variant="primary" icon={<Lock />} onClick={() => setDialog({ kind: "close" })}>
                بستن عدم‌انطباق
              </Button>
            )}
          </div>
        }
      />

      {nc.status === "OPEN" && (
        <Alert tone="info">پس از پذیرش و ریشه‌یابی توسط مسئول، می‌توان برای این مورد اقدام اصلاحی تعیین کرد.</Alert>
      )}
      {nc.status === "REJECTED" && <Alert tone="warning">این مورد رد شده و اقدامی برای آن تعیین نمی‌شود.</Alert>}

      {(nc.status === "IN_PROGRESS" || nc.status === "CLOSED") && (
        <div className="space-y-4">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <ProgressBar value={actionsProgress(nc)} className="h-2.5 min-w-40 max-w-md flex-1" label="پیشرفت اقدام‌ها" />
              <span className="text-sm font-bold text-slate-700">{actionsSummary(nc)}</span>
              {nc.actions_overdue > 0 && (
                <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-xs text-rose-800 ring-1 ring-inset ring-rose-600/20">
                  <AlarmClock className="size-3.5" />
                  {toPersianDigits(nc.actions_overdue)} اقدام دیرکرد
                </span>
              )}
            </div>
            {hint && <p className="text-xs text-slate-500">{hint}</p>}
          </div>

          {error && <ErrorBanner message={error} />}

          {actions.loading && rows.length === 0 ? (
            <SkeletonLines rows={2} />
          ) : actions.error ? (
            <ErrorBanner message={actions.error} />
          ) : rows.length === 0 ? (
            <EmptyState compact icon={<ListChecks />} message="هنوز اقدامی تعیین نشده است." />
          ) : (
            <ul className="space-y-3">
              {rows.map((action) => (
                <ActionRow
                  key={action.id}
                  action={action}
                  busy={busyId === action.id}
                  onMove={(status) => move(action, status)}
                  onDialog={(kind) => setDialog({ kind, action })}
                />
              ))}
            </ul>
          )}
        </div>
      )}

      {dialog?.kind === "add" && <ActionFormDialog ncId={nc.id} onSaved={done} onClose={() => setDialog(null)} />}
      {dialog?.kind === "edit" && (
        <ActionFormDialog ncId={nc.id} action={dialog.action} onSaved={done} onClose={() => setDialog(null)} />
      )}
      {dialog?.kind === "verify" && (
        <TextDialog
          title="تایید اقدام"
          description={`«${dialog.action.title}» انجام شده است. تایید شما به معنی بررسی و اطمینان از اجرای آن است.`}
          fieldLabel="توضیح تایید (اختیاری)"
          confirmLabel="تایید"
          required={false}
          onSubmit={(note) => post(`actions/${dialog.action.id}/verify/`, { note })()}
          onCancel={() => setDialog(null)}
        />
      )}
      {dialog?.kind === "fail" && (
        <TextDialog
          title="تایید ناموفق"
          description="اقدام درست انجام نشده یا اثر نکرده است. به مسئول آن برمی‌گردد تا دوباره انجام دهد."
          fieldLabel="دلیل"
          confirmLabel="بازگرداندن اقدام"
          danger
          onSubmit={(reason) => post(`actions/${dialog.action.id}/fail-verification/`, { reason })()}
          onCancel={() => setDialog(null)}
        />
      )}
      {dialog?.kind === "cancel" && (
        <TextDialog
          title="لغو اقدام"
          description={`«${dialog.action.title}» دیگر لازم نیست. اقدام لغوشده روی پرونده می‌ماند اما در بستن عدم‌انطباق حساب نمی‌شود.`}
          fieldLabel="دلیل لغو"
          confirmLabel="لغو اقدام"
          danger
          onSubmit={(reason) => post(`actions/${dialog.action.id}/cancel/`, { reason })()}
          onCancel={() => setDialog(null)}
        />
      )}
      {dialog?.kind === "close" && (
        <TextDialog
          title="بستن عدم‌انطباق"
          description="همهٔ اقدام‌ها انجام و تایید شده‌اند. بنویسید چگونه مطمئن شدید مشکل برطرف شده است؛ این متن روی پرونده می‌ماند."
          fieldLabel="اثربخشی اقدام‌ها"
          confirmLabel="بستن"
          onSubmit={(effectiveness_note) => post("close/", { effectiveness_note })()}
          onCancel={() => setDialog(null)}
        />
      )}
    </Card>
  );
}

function ActionRow({
  action,
  busy,
  onMove,
  onDialog,
}: {
  action: CorrectiveAction;
  busy: boolean;
  onMove: (status: ActionStatus) => void;
  onDialog: (kind: "edit" | "verify" | "fail" | "cancel") => void;
}) {
  const buttons = statusButtons(action);
  const cancelled = action.status === "CANCELLED";
  return (
    <li className={cx("space-y-2.5 rounded-xl border border-slate-200 bg-white px-4 py-3", cancelled && "bg-slate-50 opacity-75")}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h4 className={cx("min-w-0 flex-1 basis-48 font-bold text-slate-900", cancelled && "line-through")}>{action.title}</h4>
        <span className="flex flex-wrap items-center gap-1.5">
          {action.is_overdue && (
            <Badge tone="danger">
              <AlarmClock className="size-3" />
              دیرکرد
            </Badge>
          )}
          <Badge tone={ACTION_STATUS_TONE[action.status]} dot>
            {action.status_label}
          </Badge>
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
        <span className="inline-flex items-center gap-1.5">
          <Avatar name={action.assignee_name} size="xs" />
          {action.assignee_name}
          {!action.assignee_is_active && (
            <span className="inline-flex items-center gap-0.5 text-amber-700">
              <UserX className="size-3.5" />
              غیرفعال
            </span>
          )}
        </span>
        <span className={cx("inline-flex items-center gap-1", action.is_overdue && "font-bold text-rose-700")}>
          <CalendarClock className="size-3.5" />
          مهلت: {formatJalali(action.due_on)}
        </span>
        {action.completed_at && action.status !== "VERIFIED" && <span>انجام: {formatJalali(action.completed_at)}</span>}
        {action.status === "VERIFIED" && action.verified_by_name && (
          <span className="inline-flex items-center gap-1 text-emerald-700">
            <BadgeCheck className="size-3.5" />
            تایید توسط {action.verified_by_name}
            {action.verified_at ? ` · ${formatJalali(action.verified_at)}` : ""}
          </span>
        )}
        {cancelled && (
          <span className="inline-flex items-center gap-1">
            <CircleSlash className="size-3.5" />
            لغو شد
          </span>
        )}
      </div>

      {action.description && <p className="whitespace-pre-line text-sm leading-7 text-slate-700">{action.description}</p>}
      {action.verification_note && (
        <p className="rounded-lg bg-emerald-50/70 px-3 py-2 text-xs leading-6 text-emerald-900 ring-1 ring-inset ring-emerald-200">
          {action.verification_note}
        </p>
      )}
      {action.cancel_reason && (
        <p className="rounded-lg bg-slate-100 px-3 py-2 text-xs leading-6 text-slate-700">دلیل لغو: {action.cancel_reason}</p>
      )}

      {(buttons.length > 0 || action.can_verify || action.can_edit || action.can_cancel) && (
        <div className="flex flex-wrap gap-2 pt-1">
          {buttons.map((button) => (
            <Button
              key={button.status}
              size="sm"
              variant={button.forward ? "primary" : "ghost"}
              loading={busy}
              onClick={() => onMove(button.status)}
            >
              {button.label}
            </Button>
          ))}
          {action.can_verify && (
            <>
              <Button size="sm" variant="primary" icon={<BadgeCheck />} onClick={() => onDialog("verify")}>
                تایید
              </Button>
              <Button size="sm" icon={<ShieldX />} onClick={() => onDialog("fail")}>
                تایید ناموفق
              </Button>
            </>
          )}
          {action.can_edit && (
            <Button size="sm" variant="ghost" icon={<Pencil />} onClick={() => onDialog("edit")}>
              ویرایش
            </Button>
          )}
          {action.can_cancel && (
            <Button size="sm" variant="danger-ghost" icon={<CircleSlash />} onClick={() => onDialog("cancel")}>
              لغو
            </Button>
          )}
        </div>
      )}
    </li>
  );
}
