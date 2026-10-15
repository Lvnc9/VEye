from celery import shared_task
from django.conf import settings


@shared_task(name="ops.run_backup", time_limit=settings.BACKUP_TIMEOUT_SECONDS * 2, soft_time_limit=settings.BACKUP_TIMEOUT_SECONDS * 2 - 30)
def run_backup(run_id: int | None = None) -> str:
    """The nightly backup (beat, 02:30) or one started from «تنظیمات» (`run_id` of the row the view
    created, so the screen shows it as running straight away)."""
    from . import backup
    from .models import BackupRun, BackupStatus, BackupTrigger

    backup.mark_stale_runs()
    if run_id is None:
        run = BackupRun.objects.create(trigger=BackupTrigger.SCHEDULE)
    else:
        run = BackupRun.objects.filter(pk=run_id, status=BackupStatus.RUNNING).first()
        if run is None:
            return "skipped"
    return backup.perform(run).status
