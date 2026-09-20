import logging

from celery import shared_task
from django.utils import timezone

from . import loader, sources
from .files import V1Files
from .models import ImportRun, ImportStatus

logger = logging.getLogger("veye")

#: Progress is written every few documents so a long import is visible without a
#: database write per row.
PROGRESS_EVERY = 5

FAILED_UNEXPECTED = "واردسازی با یک خطای پیش‌بینی‌نشده متوقف شد. جزئیات در گزارش‌های سرور است."
FAILED_NO_DATA_DIR = "پوشهٔ داده‌های نسخهٔ ۱ یافت نشد (باید شامل saves/ یا img/ باشد)."


def _fail(run: ImportRun, message: str) -> str:
    run.status = ImportStatus.FAILED
    run.error = message[:255]
    run.finished_at = timezone.now()
    run.save(update_fields=["status", "error", "finished_at", "updated_at"])
    return "failed"


@shared_task(bind=True, name="importer.import_v1", time_limit=3600, soft_time_limit=3500)
def import_v1(self, run_id: int) -> str:
    """Run one ImportRun. Only acts on a QUEUED run, so a redelivered message is a no-op.

    The Mongo URI (if that source is used) is read from the environment *here*, in the
    worker; the message carries only the run id. Every failure ends as a FAILED run with
    a Persian message — never a stack trace with a connection string in it."""
    run = ImportRun.objects.filter(pk=run_id).first()
    if run is None or run.status != ImportStatus.QUEUED:
        return "skipped"

    run.status = ImportStatus.RUNNING
    run.started_at = timezone.now()
    run.save(update_fields=["status", "started_at", "updated_at"])

    try:
        files = V1Files(run.options.get("v1_dir", ""))
        if not files.usable:
            return _fail(run, FAILED_NO_DATA_DIR)
        rows = sources.load_rows(run.options)

        run.total = len(rows)
        run.save(update_fields=["total", "updated_at"])

        def progress(done: int, total: int):
            if done % PROGRESS_EVERY == 0 or done == total:
                ImportRun.objects.filter(pk=run.pk).update(processed=done, updated_at=timezone.now())

        result = loader.run_import(rows, files, dry_run=run.dry_run, run_id=run.pk, progress=progress)
    except sources.SourceError as error:
        return _fail(run, str(error))
    except Exception:
        logger.exception("import run %s failed", run_id)
        return _fail(run, FAILED_UNEXPECTED)

    run.status = ImportStatus.SUCCEEDED
    run.counts = result.counts
    run.report = [entry.as_dict() for entry in result.entries]
    run.processed = run.total
    run.finished_at = timezone.now()
    run.save(update_fields=["status", "counts", "report", "processed", "finished_at", "updated_at"])
    return "succeeded"
