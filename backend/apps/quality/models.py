"""The quality module (Phase 18): what went wrong, and proof that it was fixed.

A non-conformance is a recorded problem; corrective actions are the fixes; an internal audit finds
problems; a risk is a problem that has not happened yet. This file holds the first two (slices 1-2:
the non-conformance and its corrective actions) and the history every part of the module shares. Like projects, none of it is a controlled document:
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


class ActionStatus(models.TextChoices):
    """A corrective action's life. The assignee moves it TODO ↔ IN_PROGRESS → DONE; a *different*
    manager then verifies it (VERIFIED) or sends it back (IN_PROGRESS) — whoever did the work cannot be
    the one who confirms it worked. CANCELLED is the way out of an action no longer needed; nothing is
    ever deleted."""

    TODO = "TODO", "انجام نشده"
    IN_PROGRESS = "IN_PROGRESS", "در حال انجام"
    DONE = "DONE", "انجام شد، منتظر تایید"
    VERIFIED = "VERIFIED", "تایید شد"
    CANCELLED = "CANCELLED", "لغو شد"


#: An action in one of these is finished (done and checked, or dropped): it can no longer change.
FINAL_ACTION_STATUSES = (ActionStatus.VERIFIED, ActionStatus.CANCELLED)
#: An action in one of these is still the assignee's to do — the ones that can be late.
OPEN_ACTION_STATUSES = (ActionStatus.TODO, ActionStatus.IN_PROGRESS)


class CorrectiveAction(TimeStampedModel):
    """One fix for a non-conformance: who does what by when, and whether it was checked. Unlike a
    project objective it has exactly **one** assignee — a named person accountable for it, which is the
    ISO norm and keeps «who was supposed to do this?» answerable."""

    nc = models.ForeignKey(NonConformance, on_delete=models.CASCADE, related_name="actions")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assigned_corrective_actions"
    )
    due_on = models.DateField()
    status = models.CharField(max_length=12, choices=ActionStatus.choices, default=ActionStatus.TODO)
    completed_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_note = models.TextField(blank=True)
    cancel_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["due_on", "id"]
        constraints = [
            CheckConstraint(
                check=~Q(status=ActionStatus.VERIFIED) | Q(verified_at__isnull=False),
                name="action_verified_has_verified_at",
            ),
        ]
        indexes = [
            Index(fields=["nc", "status"], name="action_nc_status_idx"),
            Index(fields=["assignee", "status"], name="action_assignee_status_idx"),
        ]

    def __str__(self):
        return f"{self.nc.code}: {self.title}"


class QualityEventKind(models.TextChoices):
    NC_REPORTED = "nc_reported", "عدم‌انطباق ثبت شد"
    NC_EDITED = "nc_edited", "عدم‌انطباق ویرایش شد"
    NC_ACCEPTED = "nc_accepted", "عدم‌انطباق پذیرفته شد"
    NC_REJECTED = "nc_rejected", "عدم‌انطباق رد شد"
    NC_CLOSED = "nc_closed", "عدم‌انطباق بسته شد"
    NC_REOPENED = "nc_reopened", "عدم‌انطباق بازگشایی شد"
    ACTION_ADDED = "action_added", "اقدام اصلاحی افزوده شد"
    ACTION_EDITED = "action_edited", "اقدام اصلاحی ویرایش شد"
    ACTION_ASSIGNED = "action_assigned", "اقدام اصلاحی واگذار شد"
    ACTION_STATUS_CHANGED = "action_status_changed", "وضعیت اقدام تغییر کرد"
    ACTION_DUE_CHANGED = "action_due_changed", "مهلت اقدام تغییر کرد"
    ACTION_VERIFIED = "action_verified", "اقدام تایید شد"
    ACTION_VERIFICATION_FAILED = "action_verification_failed", "تایید اقدام ناموفق بود"
    ACTION_CANCELLED = "action_cancelled", "اقدام لغو شد"


class QualityEvent(TimeStampedModel):
    """One line of the module's history — a near-copy of `ProjectEvent`/`OrgEvent`, including the
    load-bearing decision: the actor is a *text snapshot* beside its SET_NULL foreign key, so the trail
    keeps reading correctly after someone is deactivated or changes سمت. Written by the service inside
    the same transaction as the change it records — never by a signal — so a refused change leaves no
    line."""

    nc = models.ForeignKey(NonConformance, null=True, blank=True, on_delete=models.CASCADE, related_name="events")
    #: The action it is about, if any. SET_NULL: an action is never deleted, but if one ever were its
    #: history would still read correctly through `subject_title`.
    action = models.ForeignKey(
        CorrectiveAction, null=True, blank=True, on_delete=models.SET_NULL, related_name="events"
    )
    kind = models.CharField(max_length=32, choices=QualityEventKind.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    actor_name = models.CharField(max_length=255)
    actor_title = models.CharField(max_length=255, blank=True)
    #: What the event is about, as it read at the time.
    subject_title = models.CharField(max_length=255, blank=True)
    #: A status change's before and after (the record's or the action's own status enum); for
    #: `action_due_changed` the old and new deadline as ISO dates, so the feed needs no extra columns.
    from_status = models.CharField(max_length=16, blank=True)
    to_status = models.CharField(max_length=16, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        # Forward, so nc.events.all() reads as a timeline; the feed views order newest first.
        ordering = ["created_at", "id"]
        indexes = [Index(fields=["nc", "created_at"], name="qevent_nc_time_idx")]

    def __str__(self):
        return f"{self.kind} by {self.actor_name}"
