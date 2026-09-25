/**
 * What `useApiQuery` shows for a given request — pure, so it can be unit-tested without React.
 *
 * The rule (Phase 10): a **reload of the same path keeps the last answer on screen** until the new one
 * arrives. Before this, every reload blanked `data` and flipped `loading` back to true, so a page that
 * shows a spinner while loading unmounted everything below it — the setup wizard lost the واحد the
 * user had picked after every «افزودن». A **different path** is a different question: its predecessor's
 * answer is never shown (it would put the previous node's members under a newly selected node).
 */
export interface LoadedQuery<T> {
  /** `path#reload` — identifies one request. */
  key: string;
  path: string;
  data: T | null;
  error: string | null;
}

export interface QueryState<T> {
  data: T | null;
  error: string | null;
  /** True only while nothing has arrived yet for this path. */
  loading: boolean;
  /** True while a reload of the same path is in flight and the previous answer is still shown. */
  refreshing: boolean;
}

export function queryKey(path: string, reload: number): string {
  return `${path}#${reload}`;
}

export function queryState<T>(loaded: LoadedQuery<T> | null, path: string, reload: number): QueryState<T> {
  if (!loaded || loaded.path !== path) return { data: null, error: null, loading: true, refreshing: false };
  const current = loaded.key === queryKey(path, reload);
  return { data: loaded.data, error: loaded.error, loading: false, refreshing: !current };
}

/** The value to store when a request fails: keep the last good data for the same path, drop it for another. */
export function failedQuery<T>(previous: LoadedQuery<T> | null, path: string, key: string, error: string): LoadedQuery<T> {
  return { key, path, data: previous?.path === path ? previous.data : null, error };
}
