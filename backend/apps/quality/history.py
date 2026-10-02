"""The quality history feed (Phase 18) — the «git log» rail: who reported, triaged, changed or closed
a record, and why. The same two routes as the project feed, for the same reason: every queryset starts
from `visible_nonconformances`, so an id for a record the caller cannot read behaves like one that does
not exist (`/…/{id}/activity/` is a 404; `?nc=<id>` on the cross-record feed silently returns nothing).
"""
from datetime import timedelta

from django.utils import timezone
from rest_framework.generics import ListAPIView, get_object_or_404
from rest_framework.permissions import IsAuthenticated

from apps.core.pagination import DefaultPagination

from .access import visible_nonconformances
from .models import QualityEvent, QualityEventKind
from .serializers import QualityEventSerializer

MAX_DAYS = 3650


def _filters(queryset, params):
    if kind := params.get("kind"):
        queryset = queryset.filter(kind=kind) if kind in QualityEventKind.values else queryset.none()
    days = params.get("days")
    if days and days.isdigit():
        queryset = queryset.filter(created_at__gte=timezone.now() - timedelta(days=min(int(days), MAX_DAYS)))
    return queryset


class NonConformanceActivityView(ListAPIView):
    """GET /quality/nonconformances/{id}/activity/ — one record's history, newest first."""

    serializer_class = QualityEventSerializer
    pagination_class = DefaultPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        nc = get_object_or_404(visible_nonconformances(self.request), pk=self.kwargs["pk"])
        return _filters(QualityEvent.objects.filter(nc=nc).select_related("nc").order_by("-created_at", "-id"), self.request.query_params)


class AllQualityActivityView(ListAPIView):
    """GET /quality/activity/ — the history across every record the caller may read
    (`?nc=` narrows to one, `?kind=`, `?days=`)."""

    serializer_class = QualityEventSerializer
    pagination_class = DefaultPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        visible = visible_nonconformances(self.request).values("pk")
        queryset = QualityEvent.objects.filter(nc__in=visible).select_related("nc")
        nc = self.request.query_params.get("nc")
        if nc:
            queryset = queryset.filter(nc_id=nc) if nc.isdigit() else queryset.none()
        return _filters(queryset.order_by("-created_at", "-id"), self.request.query_params)
