"""Derived numbers for the quality module — never stored.

A stored «۲ از ۳ تایید شده» is a cache that goes stale the moment an action changes, so the counts are
computed here with aggregate *subqueries* (the analogue of `projects/queries.py`): one annotated query
for a whole list, no query per row and no join that would multiply rows.

  actions_total     non-cancelled actions            (a dropped action is not part of the plan)
  actions_verified  of those, VERIFIED
  actions_overdue   TODO / IN_PROGRESS and past their deadline (DONE is waiting on a verifier, not late)

and for an audit:

  findings_total    non-conformances it raised
  findings_open     of those, still being triaged or worked (OPEN / IN_PROGRESS)
"""
from django.db.models import Count, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import OPEN_ACTION_STATUSES, ActionStatus, CorrectiveAction, NcStatus, NonConformance


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
