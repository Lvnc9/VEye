"use client";

import { useState } from "react";
import { ApiError, apiDownload } from "@/lib/api-client";
import { useCurrentUser } from "@/lib/current-user";
import { documentsExportPath, projectsExportPath } from "@/lib/reports";
import { DOCUMENT_CATEGORY_LABELS, DOCUMENT_GROUP_LABELS, DOCUMENT_STATUS_LABELS } from "@/lib/types";
import { KpiPanel } from "@/components/reports/KpiPanel";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { controlClass } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Download, FileSpreadsheet, FolderKanban } from "lucide-react";

const select = `${controlClass} h-10 px-2 text-sm`;

/** Fetch a CSV with the session's cookies and hand it to the browser as a file. (A plain link would
 *  show the server's JSON error instead of a Persian message when the session or capability is gone.) */
async function saveCsv(path: string, fallbackName: string) {
  const { blob, filename } = await apiDownload(path, fallbackName);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/** «گزارش‌ها» (Phase 17): spreadsheets of the document register and of the projects the viewer may
 *  read. Gated by `view_reports` (the server enforces it; this only hides the page). */
export default function ReportsPage() {
  const { can, loading } = useCurrentUser();
  const [group, setGroup] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [archived, setArchived] = useState(false);
  const [busy, setBusy] = useState<"documents" | "projects" | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (loading) return <LoadingBanner />;
  if (!can("view_reports")) return <ErrorBanner message="شما به گزارش‌ها دسترسی ندارید." />;

  async function run(kind: "documents" | "projects", path: string, name: string) {
    setBusy(kind);
    setError(null);
    try {
      await saveCsv(path, name);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "دریافت گزارش ممکن نشد.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="گزارش‌ها" subtitle="شاخص‌های کلیدی، و خروجی جدول‌ها برای کار با اکسل" />
      <KpiPanel />

      {error && <ErrorBanner message={error} />}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card aria-label="خروجی مستندات">
          <CardHeader title="فهرست مستندات" icon={<FileSpreadsheet />} description="هر بازنگری یک سطر — همان ستون‌ها و فیلترهای ثبت مستندات" />
          <div className="grid gap-3 sm:grid-cols-3">
            <select aria-label="گروه" value={group} onChange={(e) => setGroup(e.target.value)} className={select}>
              <option value="">همهٔ گروه‌ها</option>
              {Object.entries(DOCUMENT_GROUP_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
            <select aria-label="دسته‌بندی" value={category} onChange={(e) => setCategory(e.target.value)} className={select}>
              <option value="">همهٔ دسته‌ها</option>
              {Object.entries(DOCUMENT_CATEGORY_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
            <select aria-label="وضعیت" value={status} onChange={(e) => setStatus(e.target.value)} className={select}>
              <option value="">همهٔ وضعیت‌ها</option>
              {Object.entries(DOCUMENT_STATUS_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>
          <div className="mt-4">
            <Button
              loading={busy === "documents"}
              icon={<Download />}
              onClick={() => run("documents", documentsExportPath({ group, category, status }), "documents.csv")}
            >
              دانلود CSV مستندات
            </Button>
          </div>
        </Card>

        <Card aria-label="خروجی پروژه‌ها">
          <CardHeader title="فهرست پروژه‌ها" icon={<FolderKanban />} description="پروژه‌هایی که شما حق دیدنشان را دارید — با پیشرفت و ریزهدف‌های دیرکرد" />
          <label className="flex h-10 w-fit items-center gap-2 rounded-lg px-3 text-sm text-slate-700 ring-1 ring-inset ring-slate-200 has-[:checked]:bg-brand-50 has-[:checked]:text-brand-800">
            <input type="checkbox" className="size-4 rounded" checked={archived} onChange={(e) => setArchived(e.target.checked)} />
            فقط پروژه‌های بایگانی‌شده
          </label>
          <div className="mt-4">
            <Button
              loading={busy === "projects"}
              icon={<Download />}
              onClick={() => run("projects", projectsExportPath(archived), "projects.csv")}
            >
              دانلود CSV پروژه‌ها
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
