"""The quality module (Phase 18): what went wrong, and proof that it was fixed.

A non-conformance is a recorded problem; corrective actions are the fixes; an internal audit finds
problems; a risk is a problem that has not happened yet. This file holds the first of those (slice 1)
and the history every part of the module shares. Like projects, none of it is a controlled document:
no numbering counter, no revisions — a record's code is simply `NC-` plus its id.

Nothing here is ever deleted. A report that turns out to be nothing is *rejected*, an action that is
no longer needed is *cancelled*: the trail of what was claimed and decided is the whole point.
"""
from django.conf import settings
from django.db import models
from django.db.models import CheckConstraint, Index, Q

from apps.core.models import TimeStampedModel
from apps.organization.models import OrgNode


class NcSource(models.TextChoices):
    AUDIT = "AUDIT", "ممیزی"
    COMPLAINT = "COMPLAINT", "شکایت"
    INSPECTION = "INSPECTION", "بازرسی"
    INTERNAL = "INTERNAL", "گزارش داخلی"
    OTHER = "OTHER", "سایر"


class NcSeverity(models.TextChoices):
    MINOR = "MINOR", "جزئی"
    MAJOR = "MAJOR", "عمده"
    CRITICAL = "CRITICAL", "بحرانی"


class NcStatus(models.TextChoices):
    """Four stored states. "Action planned" and "action verified" are *derived* from the corrective
    actions (progress «۲ از ۳ تایید شده»), never stored — the same discipline as a project's progress,
    and for the same reason: a stored copy goes stale the moment an action changes."""

    OPEN = "OPEN", "ثبت‌شده، منتظر بررسی"
    IN_PROGRESS = "IN_PROGRESS", "در دست اقدام"
    CLOSED = "CLOSED", "بسته‌شده"
    REJECTED = "REJECTED", "ردشده"


class NonConformance(TimeStampedModel):
    """One recorded problem. `owner_node` says whose process it belongs to: that node's مسئول (and
    everyone above) triages it and can see it, exactly as a project's بخش decides who sees the project."""

    title = models.CharField(max_length=255)
    description = models.TextField()
    source = models.CharField(max_length=12, choices=NcSource.choices, default=NcSource.INTERNAL)
    severity = models.CharField(max_length=8, choices=NcSeverity.choices, default=NcSeverity.MINOR)
    status = models.CharField(max_length=12, choices=NcStatus.choices, default=NcStatus.OPEN)
    #: PROTECT: a node that owns records cannot be deleted (archive it) — the same rule as documents.
    owner_node = models.ForeignKey(OrgNode, on_delete=models.PROTECT, related_name="nonconformances")
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reported_nonconformances"
    )
    #: When the problem was noticed (not when it was typed in); never in the future.
    detected_on = models.DateField()
    #: The procedure or instruction it relates to — the project's «مستند پیوست» idea, for one document.
    related_document = models.ForeignKey(
        "documents.Document", null=True, blank=True, on_delete=models.PROTECT, related_name="nonconformances"
    )
    #: Written when it is accepted (ریشه‌یابی).
    root_cause = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    #: Written when it is closed: how we know the fix worked.
    effectiveness_note = models.TextField(blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            CheckConstraint(
                check=~Q(status=NcStatus.CLOSED) | Q(closed_at__isnull=False), name="nc_closed_has_closed_at"
            ),
        ]
        indexes = [
            Index(fields=["status", "owner_node"], name="nc_status_node_idx"),
            Index(fields=["owner_node", "created_at"], name="nc_node_time_idx"),
        ]

    def __str__(self):
        return f"{self.code} {self.title}"

    @property
    def code(self) -> str:
        """`NC-0042` — the id, zero-padded. No counter table: a gap after a failed save is harmless for
        a record id (this is not a controlled document number)."""
        return f"NC-{self.pk:04d}"


class QualityEventKind(models.TextChoices):
    NC_REPORTED = "nc_reported", "عدم‌انطباق ثبت شد"
    NC_EDITED = "nc_edited", "عدم‌انطباق ویرایش شد"
    NC_ACCEPTED = "nc_accepted", "عدم‌انطباق پذیرفته شد"
    NC_REJECTED = "nc_rejected", "عدم‌انطباق رد شد"
    NC_CLOSED = "nc_closed", "عدم‌انطباق بسته شد"
    NC_REOPENED = "nc_reopened", "عدم‌انطباق بازگشایی شد"


class QualityEvent(TimeStampedModel):
    """One line of the module's history — a near-copy of `ProjectEvent`/`OrgEvent`, including the
    load-bearing decision: the actor is a *text snapshot* beside its SET_NULL foreign key, so the trail
    keeps reading correctly after someone is deactivated or changes سمت. Written by the service inside
    the same transaction as the change it records — never by a signal — so a refused change leaves no
    line."""

    nc = models.ForeignKey(NonConformance, null=True, blank=True, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=32, choices=QualityEventKind.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    actor_name = models.CharField(max_length=255)
    actor_title = models.CharField(max_length=255, blank=True)
    #: What the event is about, as it read at the time.
    subject_title = models.CharField(max_length=255, blank=True)
    #: A status change's before and after (the record's own status enum).
    from_status = models.CharField(max_length=16, blank=True)
    to_status = models.CharField(max_length=16, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        # Forward, so nc.events.all() reads as a timeline; the feed views order newest first.
        ordering = ["created_at", "id"]
        indexes = [Index(fields=["nc", "created_at"], name="qevent_nc_time_idx")]

    def __str__(self):
        return f"{self.kind} by {self.actor_name}"
