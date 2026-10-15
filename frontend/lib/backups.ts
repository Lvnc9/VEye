/**
 * «پشتیبان‌گیری» in تنظیمات (Phase 20): `GET /ops/backups/`, read for the card. Pure — relative imports only.
 */

export type BackupStatus = "running" | "succeeded" | "failed";

export interface BackupRun {
  id: number;
  status: BackupStatus;
  status_label: string;
  trigger: "schedule" | "manual";
  trigger_label: string;
  requested_by: string;
  started_at: string;
  finished_at: string | null;
  db_file: string;
  media_file: string;
  size_bytes: number;
  error: string;
  pruned: boolean;
}

export interface BackupsResponse {
  runs: BackupRun[];
  keep: number;
  schedule: string;
}

/** A nightly job that has not succeeded for this long has stopped — say so loudly. */
export const BACKUP_STALE_HOURS = 36;

export interface BackupHealth {
  lastSuccess: BackupRun | null;
  running: boolean;
  /** "none" — never succeeded; "stale" — the last success is older than BACKUP_STALE_HOURS; "ok". */
  state: "none" | "stale" | "ok";
}

export function backupHealth(runs: BackupRun[], now: Date = new Date()): BackupHealth {
  const lastSuccess = runs.find((run) => run.status === "succeeded") ?? null;
  const running = runs.some((run) => run.status === "running");
  if (!lastSuccess) return { lastSuccess, running, state: "none" };
  const ageHours = (now.getTime() - new Date(lastSuccess.finished_at ?? lastSuccess.started_at).getTime()) / 3_600_000;
  return { lastSuccess, running, state: ageHours > BACKUP_STALE_HOURS ? "stale" : "ok" };
}
