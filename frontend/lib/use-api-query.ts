"use client";

import { useEffect, useState } from "react";
import { ApiError, apiGet } from "./api-client";

/** Fetch one JSON resource on mount / when `path` changes. `loading` is derived
 *  (see use-paged-query.ts for why); an error keeps the card from blanking the page. */
export function useApiQuery<T>(path: string, reload = 0) {
  const key = `${path}#${reload}`;
  const [loaded, setLoaded] = useState<{ key: string; data: T | null; error: string | null } | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiGet<T>(path)
      .then((data) => !cancelled && setLoaded({ key, data, error: null }))
      .catch(
        (err) =>
          !cancelled &&
          setLoaded({ key, data: null, error: err instanceof ApiError ? err.message : "دریافت اطلاعات ممکن نشد." }),
      );
    return () => {
      cancelled = true;
    };
  }, [path, key]);

  const current = loaded?.key === key ? loaded : null;
  return { data: current?.data ?? null, error: current?.error ?? null, loading: current === null };
}
