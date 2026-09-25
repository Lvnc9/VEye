"use client";

import { useEffect, useState } from "react";
import { ApiError, apiGet } from "./api-client";
import { failedQuery, queryKey, queryState, type LoadedQuery } from "./query-state";

/**
 * Fetch one JSON resource on mount, when `path` changes, and whenever `reload` is bumped.
 *
 * `loading` is derived (see use-paged-query.ts for why) and is true only before the first answer for
 * this path: a `reload` bump keeps the previous answer on screen and reports `refreshing` instead, so
 * a page that shows a spinner while loading does not unmount (and lose the state of) everything below
 * it after each save. A new `path` starts from nothing. The rules live in query-state.ts (tested).
 */
export function useApiQuery<T>(path: string, reload = 0) {
  const key = queryKey(path, reload);
  const [loaded, setLoaded] = useState<LoadedQuery<T> | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiGet<T>(path)
      .then((data) => !cancelled && setLoaded({ key, path, data, error: null }))
      .catch(
        (err) =>
          !cancelled &&
          setLoaded((previous) =>
            failedQuery(previous, path, key, err instanceof ApiError ? err.message : "دریافت اطلاعات ممکن نشد."),
          ),
      );
    return () => {
      cancelled = true;
    };
  }, [path, key]);

  return queryState(loaded, path, reload);
}
