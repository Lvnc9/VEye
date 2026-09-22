"""Derived numbers for projects — never stored.

A stored percentage is a cache that goes stale the moment anyone edits a weight, so progress is
computed here with aggregate *subqueries* (the analogue of documents/queries.py `with_official_pdf`):
one annotated query for a whole list, no query per row, and no join that would multiply rows.

  progress %  = Σ weight(DONE) / Σ weight(status != CANCELLED)      (None until there is anything to do)
  overdue     = due_on < today AND status NOT IN (DONE, CANCELLED)  (computed, so no Celery beat is needed)
"""
from django.db.models import Count, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import CLOSED_OBJECTIVE_STATUSES, Objective, ObjectiveStatus


def overdue_q(today=None) -> Q:
    """The overdue predicate over an Objective queryset (`?overdue=1`), in SQL."""
    return Q(due_on__lt=today or timezone.localdate()) & ~Q(status__in=CLOSED_OBJECTIVE_STATUSES)


def _aggregate(objectives, aggregate):
    return Coalesce(
        Subquery(objectives.order_by().values("project").annotate(value=aggregate).values("value")[:1]),
        Value(0),
    )


def with_progress(queryset, today=None):
    """Annotate `weight_total`, `weight_done`, `objective_count` and `overdue_count` per project."""
    today = today or timezone.localdate()
    base = Objective.objects.filter(project=OuterRef("pk"))
    live = base.exclude(status=ObjectiveStatus.CANCELLED)
    return queryset.annotate(
        weight_total=_aggregate(live, Sum("weight")),
        weight_done=_aggregate(base.filter(status=ObjectiveStatus.DONE), Sum("weight")),
        objective_count=_aggregate(base, Count("id")),
        overdue_count=_aggregate(base.filter(overdue_q(today)), Count("id")),
    )


def progress_percent(weight_done: int, weight_total: int) -> int | None:
    """0–100, rounded; None when there is no live objective to measure (a new or fully cancelled plan)."""
    if not weight_total:
        return None
    return round(100 * weight_done / weight_total)
