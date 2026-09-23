from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Capability, User
from apps.core.constants import DocumentGroup, DocumentStatus
from apps.documents import workflow
from apps.documents.models import Document

METRICS_CACHE_KEY = "dashboard:metrics:v2"
SYSTEM_INFO_CACHE_KEY = "dashboard:system_info:v2"
CACHE_TTL_SECONDS = 60


def _status_vocabulary():
    return [{"value": value, "label": label} for value, label in DocumentStatus.choices]


def _compute_metrics():
    """Group x Status count matrix backing the dashboard table.

    Every revision row is counted, so a document that has been revised shows up
    once per revision in its own status column (the earlier revisions in
    «منسوخ شده»). All four groups are always present, zero-filled, so the table
    keeps a stable shape. V_1.0's version of this table was hardcoded mock data
    (other_folder/Dashboard.py:344-350).
    """
    counts = {
        (row["group"], row["status"]): row["n"]
        for row in Document.objects.values("group", "status").annotate(n=Count("id"))
    }
    statuses = DocumentStatus.values
    rows = []
    for group_value, group_label in DocumentGroup.choices:
        per_status = {status: counts.get((group_value, status), 0) for status in statuses}
        rows.append(
            {
                "group": group_label,
                "group_value": group_value,
                "counts": per_status,
                "total": sum(per_status.values()),
            }
        )
    return {"statuses": _status_vocabulary(), "rows": rows}


def _compute_system_info():
    """Headcounts by access_roll / access_level."""
    by_roll = {r["access_roll"]: r["count"] for r in User.objects.values("access_roll").annotate(count=Count("id"))}
    by_level = {r["access_level"]: r["count"] for r in User.objects.values("access_level").annotate(count=Count("id"))}
    return {
        "total": User.objects.count(),
        "by_roll": by_roll,
        "by_level": by_level,
    }


class DashboardMetricsView(APIView):
    def get(self, request):
        data = cache.get_or_set(METRICS_CACHE_KEY, _compute_metrics, timeout=CACHE_TTL_SECONDS)
        return Response(data)


class DashboardSystemInfoView(APIView):
    def get(self, request):
        data = cache.get_or_set(SYSTEM_INFO_CACHE_KEY, _compute_system_info, timeout=CACHE_TTL_SECONDS)
        return Response(data)


#: How many documents the «منتظر اقدام شما» card lists, and how many candidates
#: are examined to count them (the card is a nudge, not a report — the register
#: filtered by status is the full list).
AWAITING_LIST_SIZE = 20
AWAITING_SCAN_LIMIT = 500


def awaiting_documents(user) -> tuple[int, dict, list]:
    """Documents waiting for this person's step: (count, count per step, the first
    AWAITING_LIST_SIZE rows). Shared by the card and the کارتابل badge so the two never disagree."""
    wanted = Q(pk__in=[])
    if user.has_capability(Capability.CREATE_DOCUMENT):
        wanted |= Q(status=DocumentStatus.DRAFT, content_saved_at__isnull=False, created_by=user)
    if user.has_capability(Capability.CONFIRM_DOCUMENT):
        wanted |= Q(status=DocumentStatus.AWAITING_CONFIRMATION)
    if user.has_capability(Capability.APPROVE_DOCUMENT):
        wanted |= Q(status=DocumentStatus.AWAITING_APPROVAL)

    candidates = (
        Document.objects.filter(wanted)
        .prefetch_related("signoffs")
        .order_by("updated_at", "id")[:AWAITING_SCAN_LIMIT]
    )
    by_step = {step: 0 for step in workflow.STEP_LABELS}
    items = []
    for document in candidates:
        flow = workflow.next_step_for(document, user)
        if not flow["can_act"]:
            continue
        by_step[flow["step"]] += 1
        if len(items) < AWAITING_LIST_SIZE:
            items.append(
                {
                    "id": document.pk,
                    "full_code": document.full_code,
                    "title": document.title,
                    "status": document.status,
                    "status_label": document.get_status_display(),
                    "step": flow["step"],
                    "step_label": workflow.STEP_LABELS[flow["step"]],
                    # The status last changed when the document last changed hands.
                    "waiting_since": document.updated_at,
                }
            )
    return sum(by_step.values()), by_step, items


class DashboardAwaitingView(APIView):
    """GET /dashboard/awaiting/ — documents waiting for the signed-in user's step.

    The closest thing to V_1.0's dead کارتابل (inbox) button. It reuses the
    workflow's own verdict (`workflow.next_step_for`), so it can never disagree with
    the register's buttons: a step the user's roll can't take, or is barred from as
    an earlier signer, is not listed. Drafts count only when the user created them
    (every author would otherwise see everyone's unsent drafts). Not cached: it is
    per-user and cheap (two queries).
    """

    def get(self, request):
        count, by_step, items = awaiting_documents(request.user)
        return Response({"count": count, "by_step": by_step, "items": items})


#: How many objectives «منتظر اقدام» lists.
INBOX_OBJECTIVES_SIZE = 20


class DashboardInboxView(APIView):
    """GET /dashboard/inbox/ — the کارتابل in numbers, for the sidebar badge (polled), plus the
    ریزهدف rows of the «منتظر اقدام» tab.

      unread_messages     unread across everything «گفتگوها» lists (chat/queries.py's definition)
      awaiting_documents  the same count as /dashboard/awaiting/
      due_objectives      open ریزهدف assigned to me, in live projects, due within
                          INBOX_DUE_SOON_DAYS days or already overdue
      total               the three added — the badge

    Chat and projects are imported inside the view (deferred): the dashboard must not become a hub
    that every app's import graph passes through.
    """

    def get(self, request):
        from apps.chat.access import chat_access_for
        from apps.chat.queries import unread_total
        from apps.projects.models import CLOSED_OBJECTIVE_STATUSES, Objective

        user = request.user
        unread = unread_total(chat_access_for(request).listed_conversations(), user)
        documents, _, _ = awaiting_documents(user)

        today = timezone.localdate()
        horizon = today + timedelta(days=settings.INBOX_DUE_SOON_DAYS)
        due = (
            Objective.objects.filter(
                assignee__user=user, due_on__lte=horizon, project__archived_at__isnull=True
            )
            .exclude(status__in=CLOSED_OBJECTIVE_STATUSES)
            .select_related("project")
            .order_by("due_on", "id")
        )
        rows = list(due[: INBOX_OBJECTIVES_SIZE + 1])
        due_count = due.count() if len(rows) > INBOX_OBJECTIVES_SIZE else len(rows)
        objectives = [
            {
                "id": objective.pk,
                "title": objective.title,
                "project": {"id": objective.project_id, "name": objective.project.name},
                "due_on": objective.due_on,
                "status": objective.status,
                "status_label": objective.get_status_display(),
                "is_overdue": objective.due_on < today,
            }
            for objective in rows[:INBOX_OBJECTIVES_SIZE]
        ]
        return Response(
            {
                "unread_messages": unread,
                "awaiting_documents": documents,
                "due_objectives": due_count,
                "total": unread + documents + due_count,
                "objectives": objectives,
            }
        )
