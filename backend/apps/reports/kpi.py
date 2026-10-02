"""The company KPI numbers (Phase 17) — computed at read time from rows that already exist, never
stored: a stored KPI is a cache that goes stale the moment someone edits history. No new model.

The definitions are deliberate and shown on the screen, so nobody has to guess what a number means:

  confirm step   SUBMITTED  → the next CONFIRMED of the same document
  approve step   CONFIRMED  → the next APPROVED  of the same document
  a return       (مرجوع) ends the attempt: the document goes back to DRAFT, and its next SUBMITTED
                 starts a *fresh* confirm step — a returned document's waiting time is not folded into
                 the next one
  return rate    RETURNED ÷ (CONFIRMED + APPROVED + RETURNED) among the reviewers' decisions in the
                 window — "of every decision a reviewer took, how many sent the document back"
  progress       Σ weight(DONE) ÷ Σ weight(not CANCELLED) over every unfinished project the viewer may
                 read — the same formula, and the same `visible_projects`, as the project list
  workload       open ریزهدف (not DONE/CANCELLED) per assignee, in those same projects

A step is counted in the window its *end* event falls in, so a step that began before the window and
finished inside it still counts.
"""
from datetime import timedelta
from statistics import median

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.core.constants import DocumentEventKind, DocumentStatus
from apps.documents.models import Document, DocumentEvent
from apps.projects.access import visible_projects
from apps.projects.models import CLOSED_OBJECTIVE_STATUSES, ObjectiveAssignee, ProjectStatus
from apps.projects.queries import progress_percent, with_progress

DEFAULT_DAYS = 90
MIN_DAYS, MAX_DAYS = 7, 730
WORKLOAD_TOP = 15

_SECONDS_PER_DAY = 86400


def clamp_days(raw) -> int:
    """`?days=` as an int within [MIN_DAYS, MAX_DAYS]; anything unreadable is the default."""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_DAYS
    return max(MIN_DAYS, min(MAX_DAYS, value))


def paired_steps(events):
    """`events`: (document_id, kind, created_at) ordered by (document_id, created_at, id). Returns
    `{"confirm": [(ended_at, timedelta)…], "approve": […]}` — pure, so it is tested without a database."""
    steps = {"confirm": [], "approve": []}
    submitted = confirmed = None
    current = None
    for document_id, kind, at in events:
        if document_id != current:
            current, submitted, confirmed = document_id, None, None
        if kind == DocumentEventKind.SUBMITTED:
            submitted, confirmed = at, None
        elif kind == DocumentEventKind.CONFIRMED:
            if submitted is not None:
                steps["confirm"].append((at, at - submitted))
            submitted, confirmed = None, at
        elif kind == DocumentEventKind.APPROVED:
            if confirmed is not None:
                steps["approve"].append((at, at - confirmed))
            submitted = confirmed = None
        elif kind == DocumentEventKind.RETURNED:
            submitted = confirmed = None
    return steps


def summarize(durations, since) -> dict:
    """count / mean / median / longest, in days, over the steps that ended on or after `since`."""
    days = [d.total_seconds() / _SECONDS_PER_DAY for ended, d in durations if ended >= since]
    if not days:
        return {"count": 0, "average_days": None, "median_days": None, "longest_days": None}
    return {
        "count": len(days),
        "average_days": round(sum(days) / len(days), 2),
        "median_days": round(median(days), 2),
        "longest_days": round(max(days), 2),
    }


def return_rate(confirmed: int, approved: int, returned: int) -> dict:
    decisions = confirmed + approved + returned
    return {
        "confirmed": confirmed,
        "approved": approved,
        "returned": returned,
        "decisions": decisions,
        "rate": round(100 * returned / decisions, 1) if decisions else None,
    }


def document_kpis(since) -> dict:
    rows = (
        DocumentEvent.objects.filter(
            kind__in=[
                DocumentEventKind.SUBMITTED, DocumentEventKind.CONFIRMED,
                DocumentEventKind.APPROVED, DocumentEventKind.RETURNED,
            ]
        )
        .order_by("document_id", "created_at", "id")
        .values_list("document_id", "kind", "created_at")
        .iterator(chunk_size=2000)
    )
    steps = paired_steps(rows)
    counts = {
        row["kind"]: row["n"]
        for row in DocumentEvent.objects.filter(created_at__gte=since).values("kind").annotate(n=Count("id"))
    }
    now = timezone.now()
    waiting = {}
    for label, status in (("confirmation", DocumentStatus.AWAITING_CONFIRMATION), ("approval", DocumentStatus.AWAITING_APPROVAL)):
        queryset = Document.objects.filter(status=status)
        oldest = queryset.order_by("updated_at").values_list("updated_at", flat=True).first()
        waiting[label] = {
            "count": queryset.count(),
            "oldest_days": round((now - oldest).total_seconds() / _SECONDS_PER_DAY, 1) if oldest else None,
        }
    return {
        "confirm_step": summarize(steps["confirm"], since),
        "approve_step": summarize(steps["approve"], since),
        "returns": return_rate(
            counts.get(DocumentEventKind.CONFIRMED, 0),
            counts.get(DocumentEventKind.APPROVED, 0),
            counts.get(DocumentEventKind.RETURNED, 0),
        ),
        "waiting_now": waiting,
        "submitted_in_window": counts.get(DocumentEventKind.SUBMITTED, 0),
    }


def project_kpis(request) -> dict:
    today = timezone.localdate()
    visible = with_progress(visible_projects(request), today).filter(archived_at__isnull=True)
    unfinished = visible.filter(status__in=[ProjectStatus.ACTIVE, ProjectStatus.ON_HOLD])
    totals = unfinished.aggregate(done=Sum("weight_done"), total=Sum("weight_total"))
    by_status = {row["status"]: row["n"] for row in visible.values("status").annotate(n=Count("id"))}
    project_ids = list(unfinished.values_list("pk", flat=True))
    open_rows = ObjectiveAssignee.objects.filter(
        objective__project_id__in=project_ids
    ).exclude(objective__status__in=CLOSED_OBJECTIVE_STATUSES)
    workload = list(
        open_rows.values("member__user_id", "member__user__full_name")
        .annotate(
            open=Count("objective_id", distinct=True),
            # `open_rows` already excludes DONE/CANCELLED, so "overdue" is only "past its deadline".
            overdue=Count("objective_id", filter=Q(objective__due_on__lt=today), distinct=True),
        )
        .order_by("-open", "-overdue", "member__user__full_name")[:WORKLOAD_TOP]
    )
    return {
        "scope_note": "پروژه‌هایی که شما حق دیدنشان را دارید",
        "unfinished_count": len(project_ids),
        "by_status": {status: by_status.get(status, 0) for status in ProjectStatus.values},
        "progress": progress_percent(totals["done"] or 0, totals["total"] or 0),
        "weight_done": totals["done"] or 0,
        "weight_total": totals["total"] or 0,
        "overdue_objectives": sum(p.overdue_count for p in unfinished),
        "projects_with_overdue": sum(1 for p in unfinished if p.overdue_count),
        "workload": [
            {
                "user": row["member__user_id"],
                "name": row["member__user__full_name"],
                "open": row["open"],
                "overdue": row["overdue"],
            }
            for row in workload
        ],
    }


def compute(request, days: int) -> dict:
    since = timezone.now() - timedelta(days=days)
    return {"days": days, "documents": document_kpis(since), "projects": project_kpis(request)}
