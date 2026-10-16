"use client";

import { useState } from "react";
import { CalendarCheck, Plus, Save, Trash2 } from "lucide-react";
import { ApiError, apiDelete, apiPatch, apiPost } from "@/lib/api-client";
import { formatJalali, jalaliOf, toPersianDigits } from "@/lib/jalali";
import { balanceYears, type Holiday, type LeavePolicy } from "@/lib/leave";
import { useApiQuery } from "@/lib/use-api-query";
import { JalaliDatePicker } from "@/components/JalaliDatePicker";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Field, inputClass, selectClass } from "@/components/ui/Field";
import { IconButton } from "@/components/ui/IconButton";
import { useToast } from "@/components/ui/Toast";

/**
 * «مرخصی» in تنظیمات (Phase 22, HR — `manage_personnel`): the annual-leave rule (days a year, how many may
 * carry over, the year balances are counted from) and the official-holiday list a day of leave does not count on.
 */
export function LeaveSettingsCard() {
  return (
    <Card aria-label="تنظیمات مرخصی">
      <CardHeader
        title="مرخصی"
        icon={<CalendarCheck />}
        description="سهم مرخصی استحقاقی و تعطیلات رسمی. جمعه‌ها خودبه‌خود تعطیل‌اند و نیازی به ثبت ندارند."
      />
      <div className="grid gap-8 lg:grid-cols-2">
        <PolicyForm />
        <HolidayList />
      </div>
    </Card>
  );
}

function PolicyForm() {
  const toast = useToast();
  const [reload, setReload] = useState(0);
  const policy = useApiQuery<LeavePolicy>("/leave/policy/", reload).data;
  if (!policy) return <p className="text-sm text-muted-foreground">در حال بارگذاری...</p>;
  return <PolicyFields key={`${policy.annual_days}:${policy.carry_max}:${policy.start_year}`} policy={policy} onSaved={() => { toast({ tone: "success", title: "قاعدهٔ مرخصی ذخیره شد." }); setReload((n) => n + 1); }} />;
}

function PolicyFields({ policy, onSaved }: { policy: LeavePolicy; onSaved: () => void }) {
  const [draft, setDraft] = useState({
    annual_days: String(policy.annual_days),
    carry_max: String(policy.carry_max),
    start_year: String(policy.start_year),
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const currentYear = jalaliOf(new Date()).jy;
  const dirty =
    draft.annual_days !== String(policy.annual_days) ||
    draft.carry_max !== String(policy.carry_max) ||
    draft.start_year !== String(policy.start_year);
  const set = (key: keyof typeof draft) => (value: string) => {
    setDraft((current) => ({ ...current, [key]: value.replace(/[۰-۹]/g, (d) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(d))) }));
    setError(null);
  };

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await apiPatch("/leave/policy/", {
        annual_days: Number(draft.annual_days),
        carry_max: Number(draft.carry_max),
        start_year: Number(draft.start_year),
      });
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ذخیره نشد.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section aria-label="قاعدهٔ مرخصی استحقاقی" className="space-y-4">
      <h3 className="text-sm font-bold text-foreground">مرخصی استحقاقی</h3>
      <Field label="سهم هر سال (روز کاری)" htmlFor="policy-days">
        <input id="policy-days" inputMode="numeric" dir="ltr" value={draft.annual_days} onChange={(e) => set("annual_days")(e.target.value)} className={inputClass} />
      </Field>
      <Field label="حداکثر انتقال به سال بعد (روز)" htmlFor="policy-carry" hint="مانده‌ای بیش از این از دست می‌رود.">
        <input id="policy-carry" inputMode="numeric" dir="ltr" value={draft.carry_max} onChange={(e) => set("carry_max")(e.target.value)} className={inputClass} />
      </Field>
      <Field label="محاسبهٔ مانده از سال" htmlFor="policy-start" hint="پیش از این سال، مانده‌ای نگه داشته نمی‌شود.">
        <select id="policy-start" value={draft.start_year} onChange={(e) => set("start_year")(e.target.value)} className={`${selectClass} w-40`}>
          {[...new Set([...balanceYears(currentYear - 3, currentYear + 1), policy.start_year])].sort().map((year) => (
            <option key={year} value={year}>
              {toPersianDigits(year)}
            </option>
          ))}
        </select>
      </Field>
      {error && <Alert tone="danger" role="alert">{error}</Alert>}
      <Button variant="primary" icon={<Save />} onClick={() => void save()} disabled={!dirty} loading={saving}>
        ذخیره
      </Button>
    </section>
  );
}

function HolidayList() {
  const toast = useToast();
  const currentYear = jalaliOf(new Date()).jy;
  const [year, setYear] = useState(currentYear);
  const [reload, setReload] = useState(0);
  const [date, setDate] = useState("");
  const [title, setTitle] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const holidays = useApiQuery<Holiday[]>(`/leave/holidays/?year=${year}`, reload);

  async function add() {
    if (!date || !title.trim()) {
      setError("روز و عنوان تعطیلی را بنویسید.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await apiPost("/leave/holidays/", { date, title });
      setDate("");
      setTitle("");
      setReload((n) => n + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ثبت نشد.");
    } finally {
      setSaving(false);
    }
  }

  async function remove(holiday: Holiday) {
    try {
      await apiDelete(`/leave/holidays/${holiday.id}/`);
      setReload((n) => n + 1);
    } catch (err) {
      toast({ tone: "danger", title: err instanceof ApiError ? err.message : "حذف نشد." });
    }
  }

  const rows = holidays.data ?? [];
  return (
    <section aria-label="تعطیلات رسمی" className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-bold text-foreground">تعطیلات رسمی</h3>
        <select aria-label="سال" value={year} onChange={(e) => setYear(Number(e.target.value))} className={`${selectClass} h-9 w-28`}>
          {balanceYears(currentYear - 1, currentYear + 1).sort().map((y) => (
            <option key={y} value={y}>
              {toPersianDigits(y)}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-wrap items-end gap-2">
        <Field label="روز" htmlFor="holiday-date" className="w-44">
          <JalaliDatePicker id="holiday-date" value={date} onChange={(iso) => setDate(iso ?? "")} />
        </Field>
        <Field label="عنوان" htmlFor="holiday-title" className="min-w-[9rem] flex-1">
          <input id="holiday-title" value={title} maxLength={255} onChange={(e) => setTitle(e.target.value)} className={inputClass} placeholder="مثال: عید فطر" />
        </Field>
        <Button icon={<Plus />} onClick={() => void add()} loading={saving}>
          افزودن
        </Button>
      </div>
      {error && <Alert tone="danger" role="alert">{error}</Alert>}
      {holidays.loading && !holidays.data ? (
        <p className="text-sm text-muted-foreground">در حال بارگذاری...</p>
      ) : rows.length === 0 ? (
        <EmptyState compact icon={<CalendarCheck />} message={`تعطیلی‌ای برای ${toPersianDigits(year)} ثبت نشده است.`} />
      ) : (
        <ul className="divide-y divide-border rounded-xl border border-border">
          {rows.map((holiday) => (
            <li key={holiday.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
              <span className="min-w-0 truncate">
                <span className="text-foreground">{holiday.title}</span>
                <span className="ms-2 text-xs text-muted-foreground">{formatJalali(holiday.date)}</span>
              </span>
              <IconButton label={`حذف ${holiday.title}`} size="sm" tone="danger" onClick={() => void remove(holiday)}>
                <Trash2 />
              </IconButton>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
