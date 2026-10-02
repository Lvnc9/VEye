from django.conf import settings
from django.db import models
from django.db.models import Index, Q, UniqueConstraint

from apps.core.models import TimeStampedModel


class NotificationKind(models.TextChoices):
    """Every kind of اعلان this app will ever write. Declared as one closed vocabulary (the
    DocumentEventKind/ProjectEventKind device) so the feed's icon/grouping never has to guess."""

    DOCUMENT_AWAITING_CONFIRMATION = "document_awaiting_confirmation", "مستند منتظر تایید شماست"
    DOCUMENT_AWAITING_APPROVAL = "document_awaiting_approval", "مستند منتظر تصویب شماست"
    DOCUMENT_APPROVED = "document_approved", "مستند تصویب و ابلاغ شد"
    DOCUMENT_RETURNED = "document_returned", "مستند مرجوع شد"
    DOCUMENT_STALLED = "document_stalled", "مستند مدتی است منتظر مانده"
    MEMBERSHIP_ADDED = "membership_added", "عضویت جدید در ساختار سازمانی"
    MEMBERSHIP_REMOVED = "membership_removed", "پایان عضویت در ساختار سازمانی"
    LEAD_ASSIGNED = "lead_assigned", "مسئولیت یک گره به شما واگذار شد"
    DELEGATION_RECEIVED = "delegation_received", "جانشینی موقت یک مسئول به شما سپرده شد"
    NC_REPORTED = "nc_reported", "عدم‌انطباق جدیدی ثبت شد"
    NC_ACCEPTED = "nc_accepted", "عدم‌انطباق شما پذیرفته شد"
    NC_REJECTED = "nc_rejected", "عدم‌انطباق شما رد شد"
    OBJECTIVE_DUE_SOON = "objective_due_soon", "ریزهدف نزدیک به مهلت است"
    OBJECTIVE_OVERDUE = "objective_overdue", "ریزهدف از مهلت گذشته است"


class Notification(TimeStampedModel):
    """One line of a person's «اعلان‌ها» feed (Phase 15) — the first *persisted* notification in
    the app. Before this, the کارتابل badge (`apps.dashboard.views.DashboardInboxView`) was a
    live count with no underlying rows: always accurate, but nothing a person could read through
    or mark as seen. This model is additive, not a replacement — `DashboardInboxView` folds its
    unread count into the same badge.

    Written in one of two ways, never by a signal:
      * **event-driven**, inside the same transaction as the change it reports
        (`apps.documents.workflow`, `apps.organization.memberships`) — the `DocumentEvent`/
        `ProjectEvent` rule, applied here;
      * **scheduled**, by a Celery beat task (`tasks.py`) for deadline-based reminders, where
        `dedupe_key` keeps a re-run from inserting the same reminder twice.

    No read model, no settings; everyone sees every notification addressed to them, with no
    opt-out, matching the project's one-channel ("فقط داخل‌برنامه") decision (2026-10-01).
    """

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    kind = models.CharField(max_length=40, choices=NotificationKind.choices)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    #: A relative path into the frontend app (e.g. "/documents/42/edit"). Blank means "nowhere to go".
    url = models.CharField(max_length=255, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    #: Set only by a scheduled reminder, to make re-running the beat task idempotent — the same
    #: device as `Membership.is_primary`'s partial unique index, applied to a non-empty string
    #: instead of a boolean. Event-driven notifications leave this blank: there is only ever one
    #: «مستند X تصویب شد» for a given approval, so nothing needs deduplicating.
    dedupe_key = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            UniqueConstraint(
                fields=["recipient", "dedupe_key"],
                condition=~Q(dedupe_key=""),
                name="uniq_notif_recipient_dedupe",
            )
        ]
        indexes = [Index(fields=["recipient", "read_at"], name="notif_recipient_unread_idx")]

    def __str__(self):
        return f"{self.title} → {self.recipient_id}"
