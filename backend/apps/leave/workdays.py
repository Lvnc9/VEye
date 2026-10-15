"""Leave in working days (Phase 22, owner's decision 2026-10-15): a day of leave is a day the person would
have worked — Fridays and the official holidays HR keeps in «تنظیمات» are free, for every leave type."""
from datetime import date, timedelta

#: date.weekday() of Friday (Monday is 0).
FRIDAY = 4


def holiday_dates(start: date, end: date) -> set[date]:
    from .models import Holiday

    return set(Holiday.objects.filter(date__range=(start, end)).values_list("date", flat=True))


def working_days(start: date, end: date, holidays: set[date] | None = None) -> int:
    """Days from `start` to `end` (both included) that are neither a Friday nor a holiday. `holidays` may be
    passed in when many spans are counted at once (a list page); otherwise it is read for this span."""
    if end < start:
        return 0
    if holidays is None:
        holidays = holiday_dates(start, end)
    count = 0
    day = start
    while day <= end:
        if day.weekday() != FRIDAY and day not in holidays:
            count += 1
        day += timedelta(days=1)
    return count


class HolidayCache:
    """Every holiday, read once — for a serializer counting many requests. (The table holds a few dozen
    rows a year.)"""

    def __init__(self):
        self._dates: set[date] | None = None

    @property
    def dates(self) -> set[date]:
        if self._dates is None:
            from .models import Holiday

            self._dates = set(Holiday.objects.values_list("date", flat=True))
        return self._dates

    def working_days(self, start: date, end: date) -> int:
        return working_days(start, end, self.dates)


def jalali_year_bounds(year: int) -> tuple[date, date]:
    """First and last Gregorian day of Jalali year `year` (1 Farvardin … 29/30 Esfand)."""
    import jdatetime

    first = jdatetime.date(year, 1, 1).togregorian()
    last = jdatetime.date(year + 1, 1, 1).togregorian() - timedelta(days=1)
    return first, last


def jalali_year_of(day: date) -> int:
    import jdatetime

    return jdatetime.date.fromgregorian(date=day).year
