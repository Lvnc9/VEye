"use client";

import { useEffect, useState } from "react";
import { ApiError, apiGet } from "./api-client";

/** Fetch one JSON resource on mount / when `path` changes. `loading` is derived
 *  (see use-paged-query.ts for why); an error keeps the card from blanking the page. */
export function useApiQuery<T>(path: string) {
  const [loaded, setLoaded] = useState<{ path: string; data: T | null; error: string | null } | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiGet<T>(path)
      .then((data) => !cancelled && setLoaded({ path, data, error: null }))
      .catch(
        (err) =>
          !cancelled &&
          setLoaded({ path, data: null, error: err instanceof ApiError ? err.message : "دریافت اطلاعات ممکن نشد." }),
      );
    return () => {
      cancelled = true;
    };
  }, [path]);

  const current = loaded?.path === path ? loaded : null;
  return { data: current?.data ?? null, error: current?.error ?? null, loading: current === null };
}
