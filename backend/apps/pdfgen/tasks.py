import hashlib
import logging

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.db import OperationalError
from django.utils import timezone

from . import adapter, provider, storage
from .models import PdfBuild, PdfKind, PdfStatus

logger = logging.getLogger("veye")

#: Shown to the user (Persian). The technical cause goes to the log.
FAILED_GENERIC = "ساخت PDF ناموفق بود. دوباره تلاش کنید."
FAILED_TIMEOUT = "ساخت PDF بیش از حد طول کشید و متوقف شد."


def _fail(build_id: int, token: str, message: str) -> None:
    PdfBuild.objects.filter(pk=build_id, token=token, status=PdfStatus.BUILDING).update(
        status=PdfStatus.FAILED, error=message, updated_at=timezone.now()
    )


@shared_task(bind=True, max_retries=2, name="pdfgen.build_pdf")
def build_pdf(self, build_id: int, token: str) -> str:
    """Render one PdfBuild and record the result.

    Idempotent and safe to redeliver: the task only acts on a row that is still
    BUILDING with *its* token, so a duplicate or superseded delivery is a no-op.
    It keeps no state between calls — everything it renders comes from the
    database and lives in local variables, so several tasks can run at once
    without touching each other.
    """
    build = PdfBuild.objects.select_related("document").filter(pk=build_id).first()
    if build is None or build.token != token or build.status != PdfStatus.BUILDING:
        return "skipped"

    try:
        data = adapter.load(build.document_id)
        pdf = provider.deliver_to_pdf(data, preview=build.kind == PdfKind.PREVIEW)
        relative = storage.relative_path(build.document, build.kind)
        storage.write_atomic(relative, pdf)
    except SoftTimeLimitExceeded:
        _fail(build_id, token, FAILED_TIMEOUT)
        return "failed"
    except (OperationalError, OSError) as exc:
        # Transient (a dropped DB connection, a full or briefly unavailable disk):
        # try again before reporting a failure.
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=5 * (self.request.retries + 1))
        logger.exception("PDF build %s failed after retries", build_id)
        _fail(build_id, token, FAILED_GENERIC)
        return "failed"
    except Exception:
        logger.exception("PDF build %s failed", build_id)
        _fail(build_id, token, FAILED_GENERIC)
        return "failed"

    updated = PdfBuild.objects.filter(pk=build_id, token=token, status=PdfStatus.BUILDING).update(
        status=PdfStatus.READY,
        path=relative,
        size=len(pdf),
        sha256=hashlib.sha256(pdf).hexdigest(),
        built_at=timezone.now(),
        error="",
        updated_at=timezone.now(),
    )
    return "ready" if updated else "superseded"
