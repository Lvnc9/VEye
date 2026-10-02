"""Derived numbers for the quality module — never stored.

A stored «۲ از ۳ تایید شده» is a cache that goes stale the moment an action changes, so the counts are
computed here with aggregate *subqueries* (the analogue of `projects/queries.py`): one annotated query
for a whole list, no query per row and no join that would multiply rows.

  actions_total     non-cancelled actions            (a dropped action is not part of the plan)
  actions_verified  of those, VERIFIED
  actions_overdue   TODO / IN_PROGRESS and past their deadline (DONE is waiting on a verifier, not late)
"""
from django.db.models import Count, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import ActionStatus, CorrectiveAction, OPEN_ACTION_STATUSES


def overdue_q(today=None):
    from django.db.models import Q

    return Q(due_on__lt=today or timezone.localdate(), status__in=OPEN_ACTION_STATUSES)


def _count(actions):
    return Coalesce(Subquery(actions.order_by().values("nc").annotate(n=Count("id")).values("n")[:1]), Value(0))


def with_action_counts(queryset, today=None):
    today = today or timezone.localdate()
    live = CorrectiveAction.objects.filter(nc=OuterRef("pk")).exclude(status=ActionStatus.CANCELLED)
    return queryset.annotate(
        actions_total=_count(live),
        actions_verified=_count(live.filter(status=ActionStatus.VERIFIED)),
        actions_overdue=_count(live.filter(overdue_q(today))),
    )
