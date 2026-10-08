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

The quality figures (Phase 18) cover the records, audits and risks the viewer may read (`visible_*` —
in practice everything, since everyone who may open Reports also holds `manage_quality`, but built that
way so it stays true if those two capabilities ever part):

  open record       a non-conformance OPEN or IN_PROGRESS
  aging             an open record's age since it was reported, in four buckets: 0-30, 31-60, 61-90, 90+ days
  time to close     reported → closed, over the records closed in the window (a reopened record counts its
                    whole life, up to its last close)
  on-time action    a corrective action verified in the window whose work was finished (`completed_at`) on
                    or before its deadline; the rate is on-time ÷ verified in the window
  overdue action    TODO / IN_PROGRESS past its deadline on a record still being worked — now
  audits            completed in the window; planned, late (planned and past its date) and running — now;
                    findings raised in the window
  risks             the heat map's counts per level over the risks still on the register, review dates
                    passed, and those with nobody named — now
"""
from datetime import timedelta
from statistics import median

from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from apps.core.constants import DocumentEventKind, DocumentStatus
from apps.documents.models import Document, DocumentEvent
from apps.projects.access import visible_projects
from apps.projects.models import CLOSED_OBJECTIVE_STATUSES, ObjectiveAssignee, ProjectStatus
from apps.projects.queries import progress_percent, with_progress
from apps.quality.access import visible_audits, visible_nonconformances, visible_risks
from apps.quality.models import (
    LIVE_RISK_STATUSES,
    OPEN_ACTION_STATUSES,
    ActionStatus,
    AuditStatus,
    CorrectiveAction,
    NcSeverity,
    NcStatus,
)
from apps.quality.queries import risk_matrix

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


AGING_BUCKETS = (("0_30", 0, 30), ("31_60", 30, 60), ("61_90", 60, 90), ("over_90", 90, None))


def quality_kpis(request, since) -> dict:
    now, today = timezone.now(), timezone.localdate()
    records = visible_nonconformances(request).order_by()
    open_records = records.filter(status__in=[NcStatus.OPEN, NcStatus.IN_PROGRESS])

    aging = {}
    for key, younger, older in AGING_BUCKETS:
        bucket = open_records.filter(created_at__lte=now - timedelta(days=younger))
        if older is not None:
            bucket = bucket.filter(created_at__gt=now - timedelta(days=older))
        aging[key] = bucket.count()

    closed = records.filter(status=NcStatus.CLOSED, closed_at__gte=since).values_list("created_at", "closed_at")
    by_status = {row["status"]: row["n"] for row in records.values("status").annotate(n=Count("id"))}
    by_severity = {row["severity"]: row["n"] for row in open_records.values("severity").annotate(n=Count("id"))}

    actions = CorrectiveAction.objects.filter(nc__in=records.values("pk"))
    verified = actions.filter(status=ActionStatus.VERIFIED, verified_at__gte=since)
    verified_count = verified.count()
    on_time = verified.filter(completed_at__isnull=False, completed_at__date__lte=F("due_on")).count()
    live_actions = actions.filter(status__in=OPEN_ACTION_STATUSES, nc__status=NcStatus.IN_PROGRESS)

    audits = visible_audits(request).order_by()
    planned = audits.filter(status=AuditStatus.PLANNED)
    risks = visible_risks(request).order_by()
    live_risks = risks.filter(status__in=LIVE_RISK_STATUSES)
    matrix = risk_matrix(risks)

    return {
        "scope_note": "مواردی که شما حق دیدنشان را دارید",
        "nonconformances": {
            "open": open_records.count(),
            "by_status": {status: by_status.get(status, 0) for status in NcStatus.values},
            "open_by_severity": {severity: by_severity.get(severity, 0) for severity in NcSeverity.values},
            "aging": aging,
            "reported_in_window": records.filter(created_at__gte=since).count(),
            "time_to_close": summarize([(end, end - start) for start, end in closed], since),
        },
        "actions": {
            "open": live_actions.count(),
            "overdue": live_actions.filter(due_on__lt=today).count(),
            "verified_in_window": verified_count,
            "on_time": on_time,
            "on_time_rate": round(100 * on_time / verified_count, 1) if verified_count else None,
        },
        "audits": {
            "completed_in_window": audits.filter(status=AuditStatus.COMPLETED, completed_at__gte=since).count(),
            "planned": planned.count(),
            "late": planned.filter(planned_on__lt=today).count(),
            "in_progress": audits.filter(status=AuditStatus.IN_PROGRESS).count(),
            "findings_in_window": records.filter(audit__isnull=False, created_at__gte=since).count(),
        },
        "risks": {
            "live": matrix["total"],
            "levels": matrix["levels"],
            "review_overdue": live_risks.filter(review_on__lt=today).count(),
            "without_owner": live_risks.filter(owner__isnull=True).count(),
        },
    }


def compute(request, days: int) -> dict:
    since = timezone.now() - timedelta(days=days)
    return {
        "days": days,
        "documents": document_kpis(since),
        "projects": project_kpis(request),
        "quality": quality_kpis(request, since),
    }
