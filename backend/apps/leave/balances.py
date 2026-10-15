"""Annual-leave balances (Phase 22, owner's decision 2026-10-15).

Only استحقاقی leave is counted against a balance. For a person and a Jalali year:

    entitlement  HR's figure for that year (LeaveEntitlement), else the policy's `annual_days`
    carried      0 in the start year; later min(carry_max, max(0, last year's remaining))
    used         working days of *approved* annual leave falling in that year (a request across Nowruz is
                 split by day)
    pending      the same for requests still waiting
    remaining    entitlement + carried - used

Nothing is stored: a changed policy, a new holiday or a cancelled request is reflected at once. Going beyond
the balance is allowed — the decider sees a warning (`exceeds`), they are not stopped."""
from dataclasses import asdict, dataclass
from datetime import date

from .models import LeaveEntitlement, LeavePolicy, LeaveRequest, LeaveStatus, LeaveType
from .workdays import HolidayCache, jalali_year_bounds, jalali_year_of


@dataclass
class Balance:
    year: int
    entitlement: int
    carried: int
    used: int
    pending: int
    remaining: int

    def as_dict(self) -> dict:
        return asdict(self)


def days_by_year(start: date, end: date, holidays: HolidayCache) -> dict[int, int]:
    """Working days of one span, split by the Jalali year they fall in."""
    result: dict[int, int] = {}
    year = jalali_year_of(start)
    while True:
        first, last = jalali_year_bounds(year)
        if first > end:
            break
        lo, hi = max(start, first), min(end, last)
        if lo <= hi:
            result[year] = result.get(year, 0) + holidays.working_days(lo, hi)
        year += 1
    return result


class Ledger:
    """One person's annual leave, read once (their entitlements and annual requests), for any year."""

    def __init__(self, user, *, policy: LeavePolicy | None = None, holidays: HolidayCache | None = None):
        self.user = user
        self.policy = policy or LeavePolicy.current()
        self.holidays = holidays or HolidayCache()
        self.entitlements = dict(LeaveEntitlement.objects.filter(user=user).values_list("year", "days"))
        self.used: dict[int, int] = {}
        self.pending: dict[int, int] = {}
        requests = LeaveRequest.objects.filter(
            requester=user, leave_type=LeaveType.ANNUAL, status__in=(LeaveStatus.APPROVED, LeaveStatus.PENDING)
        ).only("id", "starts_on", "ends_on", "status")
        self.requests = list(requests)
        for leave in self.requests:
            target = self.used if leave.status == LeaveStatus.APPROVED else self.pending
            for year, days in days_by_year(leave.starts_on, leave.ends_on, self.holidays).items():
                target[year] = target.get(year, 0) + days

    def entitlement(self, year: int) -> int:
        return self.entitlements.get(year, self.policy.annual_days)

    def balance(self, year: int) -> Balance | None:
        """None before the policy's start year — balances were not kept then."""
        start = self.policy.start_year
        if year < start:
            return None
        carried = 0
        for current in range(start, year + 1):
            entitlement = self.entitlement(current)
            remaining = entitlement + carried - self.used.get(current, 0)
            if current == year:
                return Balance(
                    year=year,
                    entitlement=entitlement,
                    carried=carried,
                    used=self.used.get(year, 0),
                    pending=self.pending.get(year, 0),
                    remaining=remaining,
                )
            carried = min(self.policy.carry_max, max(0, remaining))
        return None  # unreachable

    def warning_for(self, leave: LeaveRequest) -> dict | None:
        """For a pending annual request: the first year in which it would take more days than are left
        (counting only approved leave against the balance). None when it fits or is not tracked."""
        if leave.leave_type != LeaveType.ANNUAL or leave.status != LeaveStatus.PENDING:
            return None
        for year, days in sorted(days_by_year(leave.starts_on, leave.ends_on, self.holidays).items()):
            balance = self.balance(year)
            if balance is not None and days > balance.remaining:
                return {"year": year, "requested": days, "remaining": balance.remaining}
        return None


def current_year() -> int:
    from django.utils import timezone

    return jalali_year_of(timezone.localdate())
