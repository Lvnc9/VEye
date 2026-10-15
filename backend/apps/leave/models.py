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
    def calendar_days(self) -> int:
        """Every day from the first to the last, both included."""
        return (self.ends_on - self.starts_on).days + 1

    @property
    def days(self) -> int:
        """Working days (Phase 22, owner's decision 2026-10-15): Fridays and holidays are not counted.
        Derived, never stored — a holiday added later recounts old requests too. One query; a list page
        uses `workdays.HolidayCache` instead."""
        from .workdays import working_days

        return working_days(self.starts_on, self.ends_on)


class Holiday(models.Model):
    """An official holiday (Phase 22), kept by HR in «تنظیمات»: a day of leave that falls on it is not
    counted. Fridays need no row."""

    date = models.DateField(unique=True)
    title = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return f"{self.date} {self.title}"


class LeavePolicy(models.Model):
    """The company's annual-leave rule (Phase 22, owner's decision 2026-10-15) — one row (pk=1), kept by HR.
    Only استحقاقی leave has a balance: `annual_days` working days per Jalali year, of which at most
    `carry_max` unused days move to the next year. Balances are counted from `start_year` (the year the app
    started keeping them); HR enters each person's opening balance for that year as an entitlement."""

    annual_days = models.PositiveSmallIntegerField(default=26)
    carry_max = models.PositiveSmallIntegerField(default=9)
    start_year = models.PositiveSmallIntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def current(cls) -> "LeavePolicy":
        from .workdays import jalali_year_of

        from django.utils import timezone

        policy = cls.objects.filter(pk=1).first()
        if policy is None:
            policy, _ = cls.objects.get_or_create(pk=1, defaults={"start_year": jalali_year_of(timezone.localdate())})
        return policy


class LeaveEntitlement(models.Model):
    """HR's figure for one person and one Jalali year, replacing the policy's `annual_days` — a different
    contract, or (in the start year) the opening balance carried over from before the app."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="leave_entitlements")
    year = models.PositiveSmallIntegerField()
    days = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "year"], name="uniq_leave_entitlement_user_year")]

    def __str__(self):
        return f"{self.user_id} {self.year}: {self.days}"
