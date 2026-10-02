"""Derived numbers for the quality module — never stored.

A stored «۲ از ۳ تایید شده» is a cache that goes stale the moment an action changes, so the counts are
computed here with aggregate *subqueries* (the analogue of `projects/queries.py`): one annotated query
for a whole list, no query per row and no join that would multiply rows.

  actions_total     non-cancelled actions            (a dropped action is not part of the plan)
  actions_verified  of those, VERIFIED
  actions_overdue   TODO / IN_PROGRESS and past their deadline (DONE is waiting on a verifier, not late)

for a risk (`risk_level`, `with_risk_score`, `risk_matrix`):

  score             likelihood × impact — never a column
  level             the band the score falls in (RISK_LEVELS: the one definition; `lib/quality.ts` mirrors it)

and for an audit:

  findings_total    non-conformances it raised
  findings_open     of those, still being triaged or worked (OPEN / IN_PROGRESS)
"""
from django.db.models import Count, F, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import (
    LIVE_RISK_STATUSES,
    OPEN_ACTION_STATUSES,
    RISK_SCALE,
    ActionStatus,
    CorrectiveAction,
    NcStatus,
    NonConformance,
)


def overdue_q(today=None):
    from django.db.models import Q

    return Q(due_on__lt=today or timezone.localdate(), status__in=OPEN_ACTION_STATUSES)


def _count_by(rows, key):
    return Coalesce(Subquery(rows.order_by().values(key).annotate(n=Count("id")).values("n")[:1]), Value(0))


def _count(actions):
    return _count_by(actions, "nc")


def with_action_counts(queryset, today=None):
    today = today or timezone.localdate()
    live = CorrectiveAction.objects.filter(nc=OuterRef("pk")).exclude(status=ActionStatus.CANCELLED)
    return queryset.annotate(
        actions_total=_count(live),
        actions_verified=_count(live.filter(status=ActionStatus.VERIFIED)),
        actions_overdue=_count(live.filter(overdue_q(today))),
    )


def with_finding_counts(queryset):
    """An audit list's «۳ یافته، ۱ باز» — counted over *every* finding of the audit, whatever the viewer
    may read of them (a number, not a record); the people who can read the audit can read its findings
    in all but a quality manager's edge case, which a bare count does not leak."""
    findings = NonConformance.objects.filter(audit=OuterRef("pk"))
    return queryset.annotate(
        findings_total=_count_by(findings, "audit"),
        findings_open=_count_by(findings.filter(status__in=[NcStatus.OPEN, NcStatus.IN_PROGRESS]), "audit"),
    )


# -- risks ---------------------------------------------------------------------

#: (key, Persian label, lowest score, highest score). Likelihood and impact are each 1-5, so a score is
#: 1-25 and only 1, 2, 3, 4, 5, 6, 8, 9, 10, 12, 15, 16, 20 and 25 can occur — the bands cover the whole
#: range regardless.
RISK_LEVELS = (
    ("low", "کم", 1, 4),
    ("medium", "متوسط", 5, 9),
    ("high", "زیاد", 10, 14),
    ("critical", "بحرانی", 15, 25),
)
RISK_LEVEL_KEYS = tuple(key for key, _, _, _ in RISK_LEVELS)


def risk_level(score: int) -> str:
    """The band a score falls in."""
    for key, _, low, high in RISK_LEVELS:
        if low <= score <= high:
            return key
    raise ValueError(f"a risk score is 1-25, not {score}")


def risk_level_label(level: str) -> str:
    return next(label for key, label, _, _ in RISK_LEVELS if key == level)


def with_risk_score(queryset):
    """Annotate `score` so a list can sort and filter by it in the database."""
    return queryset.annotate(score=F("likelihood") * F("impact"))


def filter_by_level(queryset, level: str):
    """Risks in one band (needs `with_risk_score`); an unknown level matches nothing."""
    for key, _, low, high in RISK_LEVELS:
        if key == level:
            return queryset.filter(score__gte=low, score__lte=high)
    return queryset.none()


def risk_matrix(queryset, statuses=LIVE_RISK_STATUSES) -> dict:
    """The 5×5 heat map's numbers: how many risks sit in each (likelihood, impact) cell, all 25 cells
    always present (zeros included, so a screen never has to fill gaps), plus the total and the count per
    level. Counted over the given statuses — by default the ones still on the register."""
    counts = {
        (row["likelihood"], row["impact"]): row["n"]
        for row in queryset.filter(status__in=statuses).order_by().values("likelihood", "impact").annotate(n=Count("id"))
    }
    cells = [
        {
            "likelihood": likelihood, "impact": impact, "score": likelihood * impact,
            "level": risk_level(likelihood * impact), "count": counts.get((likelihood, impact), 0),
        }
        for likelihood in reversed(RISK_SCALE)  # likelihood 5 first: the grid is drawn with the worst at the top
        for impact in RISK_SCALE
    ]
    levels = {key: sum(cell["count"] for cell in cells if cell["level"] == key) for key in RISK_LEVEL_KEYS}
    return {"cells": cells, "total": sum(levels.values()), "levels": levels}
