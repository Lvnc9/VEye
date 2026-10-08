"""Leave requests (Phase 19, employee self-service) — the first thing a person asks of the company
through the app rather than of a document.

The owner's decisions (2026-10-08): the **requester's مسئول** approves — the lead of the node they sit
in or of any node above it (so a temporary cover counts, through `OrgAccess`), with the مدیر عامل able
to decide any request and the only one left when nobody leads; **types only, no balances** (days are
recorded and counted, not deducted from an entitlement).

The row is its own trail (no event table): when it was asked (`created_at`), who decided, when and why
(`decided_by` + a name snapshot, `decided_at`, `decision_note`), and when it was cancelled. Nothing is
deleted: a request is rejected or cancelled.
"""
from django.conf import settings
from django.db import models
from django.db.models import CheckConstraint, F, Index, Q

from apps.core.models import TimeStampedModel
from apps.organization.models import OrgNode


class LeaveType(models.TextChoices):
    ANNUAL = "ANNUAL", "استحقاقی"
    SICK = "SICK", "استعلاجی"
    UNPAID = "UNPAID", "بدون حقوق"


class LeaveStatus(models.TextChoices):
    PENDING = "PENDING", "منتظر تایید"
    APPROVED = "APPROVED", "تایید شد"
    REJECTED = "REJECTED", "رد شد"
    CANCELLED = "CANCELLED", "لغو شد"


#: A request in one of these holds the days: a new one may not overlap it.
HOLDING_STATUSES = (LeaveStatus.PENDING, LeaveStatus.APPROVED)


class LeaveRequest(TimeStampedModel):
    """One request for days off. `node` is where the requester sat when they asked (their primary
    membership): it decides who approves, and stays put if they move later — the request is judged by
    the unit it was made in. SET_NULL with a name snapshot: a node is deleted only once empty, and the
    request must outlive it."""

    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="leave_requests")
    node = models.ForeignKey(OrgNode, null=True, blank=True, on_delete=models.SET_NULL, related_name="leave_requests")
    node_name = models.CharField(max_length=255, blank=True)
    leave_type = models.CharField(max_length=8, choices=LeaveType.choices, default=LeaveType.ANNUAL)
    #: Both inclusive. A date in the past is allowed: sick leave is usually recorded afterwards.
    starts_on = models.DateField()
    ends_on = models.DateField()
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=LeaveStatus.choices, default=LeaveStatus.PENDING)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    decided_by_name = models.CharField(max_length=255, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-starts_on", "-id"]
        constraints = [
            CheckConstraint(check=Q(ends_on__gte=F("starts_on")), name="leave_ends_after_it_starts"),
            CheckConstraint(
                check=~Q(status__in=[LeaveStatus.APPROVED, LeaveStatus.REJECTED]) | Q(decided_at__isnull=False),
                name="leave_decided_has_decided_at",
            ),
        ]
        indexes = [
            Index(fields=["status", "node"], name="leave_status_node_idx"),
            Index(fields=["requester", "starts_on"], name="leave_requester_start_idx"),
        ]

    def __str__(self):
        return f"{self.requester} {self.starts_on}→{self.ends_on}"

    @property
    def days(self) -> int:
        """Calendar days, both ends included — derived, never stored. (No weekend or holiday arithmetic:
        that is a balance rule, and balances are not kept.)"""
        return (self.ends_on - self.starts_on).days + 1
