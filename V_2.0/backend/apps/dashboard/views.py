from django.core.cache import cache
from django.db.models import Count
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.core.constants import DocumentGroup, DocumentStatus
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
