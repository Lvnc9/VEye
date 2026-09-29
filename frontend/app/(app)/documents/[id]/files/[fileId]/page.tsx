"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Download, FileDown } from "lucide-react";
import { ApiError, apiDownload } from "@/lib/api-client";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
import { Card } from "@/components/ui/Card";
import { buttonClass } from "@/components/ui/Button";

/**
 * The page an attached file's copied link opens (`/documents/<id>/files/<fid>`): signed-out visitors
 * are sent to /login by proxy.ts and come back here; a signed-in one gets the file saved at once.
 */
export default function AttachedFilePage() {
  const { id, fileId } = useParams<{ id: string; fileId: string }>();
  const [state, setState] = useState<{ status: "loading" } | { status: "done"; name: string } | { status: "error"; message: string }>({
    status: "loading",
  });
  const started = useRef<string | null>(null);

  const download = useCallback(async () => {
    setState({ status: "loading" });
    try {
      const { blob, filename } = await apiDownload(`/documents/${id}/files/${fileId}/download/`, "پرونده");
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 10_000);
      setState({ status: "done", name: filename });
    } catch (err) {
      setState({
        status: "error",
        message:
          err instanceof ApiError && err.status === 404
            ? "این فایل پیدا نشد؛ ممکن است از مستند حذف شده باشد."
            : err instanceof ApiError
              ? err.message
              : "دریافت فایل ممکن نشد.",
      });
    }
  }, [id, fileId]);

  useEffect(() => {
    // Once per link (React strict mode runs effects twice in development).
    const key = `${id}/${fileId}`;
    if (started.current === key) return;
    started.current = key;
    void download();
  }, [id, fileId, download]);

  return (
    <div className="mx-auto max-w-lg space-y-4 pt-6">
      {state.status === "loading" && <LoadingBanner label="در حال دریافت فایل..." />}
      {state.status === "error" && <ErrorBanner message={state.message} />}
      {state.status === "done" && (
        <Card className="space-y-4 p-6 text-center">
          <FileDown className="mx-auto size-10 text-brand-600" />
          <div className="space-y-1">
            <p className="font-bold text-slate-900">فایل دریافت شد</p>
            <p className="text-sm text-slate-600">
              <bdi>{state.name}</bdi>
            </p>
          </div>
          <button type="button" onClick={() => void download()} className={buttonClass({ variant: "primary" })}>
            <Download className="size-4" />
            دریافت دوباره
          </button>
        </Card>
      )}
      <p className="text-center text-sm">
        <Link href={`/documents/${id}/edit`} className="text-brand-700 hover:underline">
          بازگشت به مستند
        </Link>
      </p>
    </div>
  );
}
