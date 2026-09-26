"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ApiError, apiGet } from "@/lib/api-client";
import type { ContentResponse } from "@/lib/types";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
import { ClassicDesigner } from "@/components/designer/ClassicDesigner";

/** طراحی مستند: loads the body once, then hands it to the editor for its kind. */
export default function DocumentDesignerPage() {
  const { id } = useParams<{ id: string }>();
  const [initial, setInitial] = useState<ContentResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  // State is only written from the async result, never synchronously in the
  // effect body (react-hooks/set-state-in-effect).
  useEffect(() => {
    let cancelled = false;
    apiGet<ContentResponse>(`/documents/${id}/content/`)
      .then((response) => {
        if (!cancelled) setInitial(response);
      })
      .catch((err) => {
        if (!cancelled) setLoadError(err instanceof ApiError ? err.message : "دریافت مستند ممکن نشد.");
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (loadError) return <ErrorBanner message={loadError} />;
  if (!initial) return <LoadingBanner />;
  return <ClassicDesigner key={initial.document.id} initial={initial} />;
}
