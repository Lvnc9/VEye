import { describe, expect, it } from "vitest";
import { failedQuery, queryKey, queryState, type LoadedQuery } from "./query-state";

const loaded = (path: string, reload: number, data: string | null, error: string | null = null): LoadedQuery<string> => ({
  key: queryKey(path, reload),
  path,
  data,
  error,
});

describe("queryState", () => {
  it("is loading before anything arrives", () => {
    expect(queryState(null, "/a/", 0)).toEqual({ data: null, error: null, loading: true, refreshing: false });
  });

  it("shows the answer for the current request", () => {
    expect(queryState(loaded("/a/", 0, "x"), "/a/", 0)).toEqual({ data: "x", error: null, loading: false, refreshing: false });
  });

  it("keeps the previous answer on screen while the same path reloads", () => {
    // The setup-wizard bug: a reload used to blank the data and unmount the wizard.
    expect(queryState(loaded("/a/", 0, "x"), "/a/", 1)).toEqual({ data: "x", error: null, loading: false, refreshing: true });
  });

  it("never shows another path's answer", () => {
    // NodePanel: the previous node's members must not appear under a newly selected node.
    expect(queryState(loaded("/nodes/1/", 0, "x"), "/nodes/2/", 0)).toEqual({
      data: null,
      error: null,
      loading: true,
      refreshing: false,
    });
  });
});

describe("failedQuery", () => {
  it("keeps the last good data of the same path next to the error", () => {
    const failed = failedQuery(loaded("/a/", 0, "x"), "/a/", queryKey("/a/", 1), "خطا");
    expect(queryState(failed, "/a/", 1)).toEqual({ data: "x", error: "خطا", loading: false, refreshing: false });
  });

  it("drops another path's data", () => {
    expect(failedQuery(loaded("/a/", 0, "x"), "/b/", queryKey("/b/", 0), "خطا").data).toBeNull();
  });
});
