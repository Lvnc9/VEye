from django.conf import settings
from django.db import models


class BackupStatus(models.TextChoices):
    RUNNING = "running", "در حال انجام"
    SUCCEEDED = "succeeded", "موفق"
    FAILED = "failed", "ناموفق"


class BackupTrigger(models.TextChoices):
    SCHEDULE = "schedule", "زمان‌بندی شبانه"
    MANUAL = "manual", "دستی"


class BackupRun(models.Model):
    """One backup (Phase 20, owner's decision 2026-10-15): a PostgreSQL dump plus an archive of `media/`,
    written to `BACKUP_DIR` (`./backups` beside the compose file). The files are named after the run's
    start; the last `BACKUP_KEEP` successful sets are kept and older ones are deleted (`pruned`)."""

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=BackupStatus.choices, default=BackupStatus.RUNNING)
    trigger = models.CharField(max_length=10, choices=BackupTrigger.choices)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    db_file = models.CharField(max_length=255, blank=True)
    media_file = models.CharField(max_length=255, blank=True)
    size_bytes = models.BigIntegerField(default=0)
    error = models.TextField(blank=True)
    pruned = models.BooleanField(default=False)

    class Meta:
        ordering = ["-started_at", "-id"]

    def __str__(self):
        return f"backup {self.pk} {self.status} {self.started_at:%Y-%m-%d %H:%M}"
