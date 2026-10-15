"""Periodic review of controlled documents (Phase 21, owner's decision 2026-10-15).

ISO-style document control asks that a document in force be looked at again on a schedule. Each document
carries `review_interval_months` (the company default, 12, from «تنظیمات»; 0 = none) and, while it is
UNDER_CONTROL, `review_due_on`. The clock (re)starts when a revision is approved or when an author records
«بازنگری شد — بدون تغییر» (`workflow.mark_reviewed`); a superseded revision has no due date. The register
filters on it, and a beat task reminds the people who may write it `REVIEW_NOTICE_DAYS` before."""
import calendar
from datetime import date

from django.conf import settings
from django.utils import timezone

MAX_INTERVAL_MONTHS = 60


def add_months(start: date, months: int) -> date:
    """`start` plus whole calendar months; the 31st becomes the month's last day when it has fewer."""
    index = start.month - 1 + months
    year, month = start.year + index // 12, index % 12 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def due_date_from(start: date, interval_months: int) -> date | None:
    return add_months(start, interval_months) if interval_months > 0 else None


def notice_days() -> int:
    return settings.DOCUMENT_REVIEW_NOTICE_DAYS


def review_state(due_on: date | None, today: date | None = None) -> str | None:
    """"overdue" | "due" (within the notice window) | None — for the register's badge."""
    if due_on is None:
        return None
    today = today or timezone.localdate()
    if due_on < today:
        return "overdue"
    if due_on <= today + timezone.timedelta(days=notice_days()):
        return "due"
    return None
