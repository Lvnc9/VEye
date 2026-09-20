import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import UniqueConstraint
from django.utils import timezone

from apps.core.models import TimeStampedModel


class PdfKind(models.TextChoices):
    #: The issued PDF of a finalized revision. One current file, replaced by a rebuild.
    OFFICIAL = "official", "رسمی"
    #: A watermarked «پیش نمایش» (V_1.0 `preview_mode`), rendered on demand for
    #: any revision, drafts included. Never the issued copy.
    PREVIEW = "preview", "پیش‌نمایش"


class PdfStatus(models.TextChoices):
    BUILDING = "building", "در حال ساخت"
    READY = "ready", "آماده"
    FAILED = "failed", "ناموفق"


#: A BUILDING row older than this is treated as abandoned (the worker was
#: killed — the hard task limit is CELERY_TASK_TIME_LIMIT, 300 s by default) and
#: may be rebuilt instead of blocking the document forever.
BUILD_STALE_AFTER = timedelta(seconds=settings.CELERY_TASK_TIME_LIMIT + 60)


class PdfBuild(TimeStampedModel):
    """The state of one document's PDF of one kind.

    One row per (document, kind), reused by every rebuild: the file is replaced
    in place, so the row always describes the file that is on disk. The register
    list reads `status`/`built_at` of the OFFICIAL row through a subquery — it
    never opens or renders a PDF.
    """

    document = models.ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="pdf_builds")
    kind = models.CharField(max_length=16, choices=PdfKind.choices)
    status = models.CharField(max_length=16, choices=PdfStatus.choices, default=PdfStatus.BUILDING)

    # Identifies the current attempt. The worker only records its result if the
    # row still carries its token, so a superseded (stale) task can never
    # overwrite a newer build's result.
    token = models.CharField(max_length=32, default="")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    requested_at = models.DateTimeField(default=timezone.now)

    # Set when a build succeeds: where the file is (relative to MEDIA_ROOT), what
    # it is, and when it was made. Kept across a failed rebuild — the previous
    # file is still there and still downloadable.
    path = models.CharField(max_length=255, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    built_at = models.DateTimeField(null=True, blank=True)

    error = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [UniqueConstraint(fields=["document", "kind"], name="uniq_pdf_build_per_kind")]

    def __str__(self):
        return f"{self.document.full_code} {self.kind}: {self.status}"

    @staticmethod
    def new_token() -> str:
        return uuid.uuid4().hex

    @property
    def is_stale(self) -> bool:
        return self.status == PdfStatus.BUILDING and timezone.now() - self.requested_at > BUILD_STALE_AFTER

    @property
    def has_file(self) -> bool:
        return bool(self.path) and self.built_at is not None
