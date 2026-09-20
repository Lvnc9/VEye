import logging

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.core.exceptions import ConflictError
from apps.documents.models import Document

from .models import PdfBuild, PdfKind, PdfStatus
from .tasks import build_pdf

logger = logging.getLogger("veye")


def get_build(document_id: int, kind: str) -> PdfBuild | None:
    return PdfBuild.objects.filter(document_id=document_id, kind=kind).first()


@transaction.atomic
def request_build(*, user, document_id: int, kind: str) -> PdfBuild:
    """Start (or restart) a build. Returns the row in BUILDING state; the task is
    queued once the transaction commits, so a worker can never pick up a row the
    database does not have yet.

    A second request while a build is genuinely running is refused (409) rather
    than queued behind it; a row stuck BUILDING past the task's hard time limit
    is treated as abandoned and may be rebuilt.
    """
    try:
        document = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        raise NotFound("مستند یافت نشد.")

    # The issued PDF exists only for a revision that has been through control; a
    # draft can only be previewed (watermarked).
    if kind == PdfKind.OFFICIAL and not document.is_finalized:
        raise ConflictError(
            "PDF رسمی فقط برای مستندات نهایی‌شده ساخته می‌شود. برای مشاهده از «نمایش» استفاده کنید.",
            code="not_finalized",
        )

    build, created = PdfBuild.objects.select_for_update().get_or_create(
        document=document, kind=kind, defaults={"token": PdfBuild.new_token()}
    )
    if not created and build.status == PdfStatus.BUILDING and not build.is_stale:
        raise ConflictError(
            "ساخت این PDF هم‌اکنون در حال انجام است.", code="build_in_progress", build_id=build.pk
        )

    build.token = PdfBuild.new_token()
    build.status = PdfStatus.BUILDING
    build.requested_by = user
    build.requested_at = timezone.now()
    build.error = ""
    build.save()

    build_id, token = build.pk, build.token
    transaction.on_commit(lambda: _dispatch(build_id, token))
    return build


def _dispatch(build_id: int, token: str) -> None:
    try:
        build_pdf.delay(build_id, token)
    except Exception:
        # The broker is unreachable: nothing will ever run this build, so say so
        # now instead of leaving the row BUILDING until it goes stale.
        logger.exception("Could not queue PDF build %s", build_id)
        PdfBuild.objects.filter(pk=build_id, token=token, status=PdfStatus.BUILDING).update(
            status=PdfStatus.FAILED, error="سرویس ساخت PDF در دسترس نیست. کمی بعد دوباره تلاش کنید."
        )
