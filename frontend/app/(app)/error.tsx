"use client";

import { useEffect } from "react";
import { RotateCcw, TriangleAlert } from "lucide-react";
import { ErrorScreen } from "@/components/ErrorScreen";
import { Button } from "@/components/ui/Button";

/** A screen threw while rendering. The sidebar and top bar stay; only this page is replaced (Next 16
 *  gives the boundary `retry`, which re-fetches and re-renders the segment). */
export default function AppError({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <ErrorScreen
      icon={<TriangleAlert />}
      title="مشکلی پیش آمد"
      message="این صفحه به‌درستی بارگذاری نشد. دوباره تلاش کنید؛ اگر ادامه داشت، به مدیر سامانه خبر دهید."
      actions={
        <Button variant="primary" icon={<RotateCcw />} onClick={() => retry()}>
          تلاش دوباره
        </Button>
      }
    />
  );
}
