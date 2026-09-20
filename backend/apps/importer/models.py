from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class ImportStatus(models.TextChoices):
    QUEUED = "queued", "در صف"
    RUNNING = "running", "در حال اجرا"
    SUCCEEDED = "succeeded", "موفق"
    FAILED = "failed", "ناموفق"


class ImportRun(TimeStampedModel):
    """One run of `manage.py import_v1` — a dry run or a real one.

    The run is the durable record the Celery job writes as it goes: progress while
    it works, then the counts and the per-document report. `options` holds only
    *non-secret* settings (which source, the **name** of the environment variable
    that carries the Mongo URI, directories) — the URI itself is read from the
    environment when the job runs and is never stored, logged or sent through the
    broker.
    """

    status = models.CharField(max_length=16, choices=ImportStatus.choices, default=ImportStatus.QUEUED)
    dry_run = models.BooleanField(default=True)
    options = models.JSONField(default=dict, blank=True)

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    total = models.PositiveIntegerField(default=0)
    processed = models.PositiveIntegerField(default=0)
    #: {"total", "created" | "would_create", "skipped", "errors", "warnings", "superseded"}
    counts = models.JSONField(default=dict, blank=True)
    #: [{"position", "code", "title", "action", "notes": [{"level", "code", "message"}]}]
    report = models.JSONField(default=list, blank=True)
    error = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        mode = "dry-run" if self.dry_run else "commit"
        return f"import #{self.pk} ({mode}): {self.status}"
