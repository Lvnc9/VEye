import { describe, expect, it } from "vitest";
import { backupHealth, type BackupRun } from "./backups";

const run = (over: Partial<BackupRun>): BackupRun => ({
  id: 1,
  status: "succeeded",
  status_label: "",
  trigger: "schedule",
  trigger_label: "",
  requested_by: "",
  started_at: "2026-10-15T02:30:00Z",
  finished_at: "2026-10-15T02:31:00Z",
  db_file: "a.dump",
  media_file: "a-media.tar.gz",
  size_bytes: 10,
  error: "",
  pruned: false,
  ...over,
});

describe("backupHealth", () => {
  const now = new Date("2026-10-15T12:00:00Z");

  it("is fine after last night's backup", () => {
    const health = backupHealth([run({ id: 2 }), run({ id: 1, started_at: "2026-10-14T02:30:00Z" })], now);
    expect(health.state).toBe("ok");
    expect(health.lastSuccess?.id).toBe(2);
    expect(health.running).toBe(false);
  });

  it("skips failures to find the last good one, and calls it stale when old", () => {
    const health = backupHealth(
      [
        run({ id: 3, status: "failed", finished_at: "2026-10-15T02:31:00Z" }),
        run({ id: 2, status: "failed" }),
        run({ id: 1, finished_at: "2026-10-13T02:31:00Z" }),
      ],
      now,
    );
    expect(health.lastSuccess?.id).toBe(1);
    expect(health.state).toBe("stale");
  });

  it("says when there has never been one, and when one is running", () => {
    const health = backupHealth([run({ status: "running", finished_at: null })], now);
    expect(health).toEqual({ lastSuccess: null, running: true, state: "none" });
  });
});
