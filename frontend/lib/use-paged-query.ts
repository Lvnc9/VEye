"use client";

import { useEffect, useState } from "react";
import { ApiError, apiGet } from "./api-client";
import type { Paginated } from "./types";

type Params = Record<string, string | number>;

/**
 * Fetch one page of a paginated endpoint whenever `path`, `params` or `reload` change.
 *
 * `loading` is *derived* ("the answer for the current inputs hasn't arrived") rather
 * than set at the start of the effect — this project's lint config makes a
 * synchronous setState in an effect an error — and the previous rows stay on
 * screen until the new ones arrive.
 */
export function usePagedQuery<T>(path: string, params: Params, reload = 0) {
  const key = JSON.stringify({ path, params, reload });
  const [loaded, setLoaded] = useState<{ key: string; rows: T[]; count: number; error: string | null } | null>(null);

  useEffect(() => {
    let cancelled = false;
    const { path: p, params: q } = JSON.parse(key) as { path: string; params: Params };
    apiGet<Paginated<T>>(p, q)
      .then((response) => {
        if (!cancelled) setLoaded({ key, rows: response.results, count: response.count, error: null });
      })
      .catch((err) => {
        if (cancelled) return;
        setLoaded({
          key,
          rows: [],
          count: 0,
          error: err instanceof ApiError ? err.message : "دریافت اطلاعات ممکن نشد.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [key]);

  return {
    rows: loaded?.rows ?? [],
    count: loaded?.count ?? 0,
    error: loaded?.error ?? null,
    loading: loaded?.key !== key,
  };
}
