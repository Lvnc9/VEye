from django.core.cache import cache
from django.db.models import Count, Q
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
        user = request.user
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
        return Response({"count": sum(by_step.values()), "by_step": by_step, "items": items})
