"""The quality history feed (Phase 18) — the «git log» rail: who reported, triaged, changed or closed
a record, and why. The same two routes as the project feed, for the same reason: every queryset starts
from `visible_nonconformances` / `visible_audits` / `visible_risks`, so an id for a record the caller
cannot read behaves like one that does not exist (`/…/{id}/activity/` is a 404; `?nc=<id>`,
`?audit=<id>` and `?risk=<id>` on the cross-record feed silently return nothing).
"""
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework.generics import ListAPIView, get_object_or_404
from rest_framework.permissions import IsAuthenticated

from apps.core.pagination import DefaultPagination

from .access import visible_audits, visible_nonconformances, visible_risks
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
        return _filters(QualityEvent.objects.filter(nc=nc).select_related("nc", "audit", "risk").order_by("-created_at", "-id"), self.request.query_params)


class AuditActivityView(ListAPIView):
    """GET /quality/audits/{id}/activity/ — one audit's history, newest first: planned, started,
    completed or cancelled, and each finding it raised."""

    serializer_class = QualityEventSerializer
    pagination_class = DefaultPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        audit = get_object_or_404(visible_audits(self.request), pk=self.kwargs["pk"])
        return _filters(
            QualityEvent.objects.filter(audit=audit).select_related("nc", "audit", "risk").order_by("-created_at", "-id"),
            self.request.query_params,
        )


class RiskActivityView(ListAPIView):
    """GET /quality/risks/{id}/activity/ — one risk's history, newest first: created, edited, re-assessed
    («۳×۴ ← ۴×۴») and every status move."""

    serializer_class = QualityEventSerializer
    pagination_class = DefaultPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        risk = get_object_or_404(visible_risks(self.request), pk=self.kwargs["pk"])
        return _filters(
            QualityEvent.objects.filter(risk=risk).select_related("nc", "audit", "risk").order_by("-created_at", "-id"),
            self.request.query_params,
        )


class AllQualityActivityView(ListAPIView):
    """GET /quality/activity/ — the history across every record, audit and risk the caller may read
    (`?nc=`, `?audit=` or `?risk=` narrows to one, `?kind=`, `?days=`)."""

    serializer_class = QualityEventSerializer
    pagination_class = DefaultPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        records = visible_nonconformances(self.request).values("pk")
        audits = visible_audits(self.request).values("pk")
        risks = visible_risks(self.request).values("pk")
        queryset = QualityEvent.objects.filter(
            Q(nc__in=records) | Q(audit__in=audits) | Q(risk__in=risks)
        ).select_related("nc", "audit", "risk")
        params = self.request.query_params
        for param, column in (("nc", "nc_id"), ("audit", "audit_id"), ("risk", "risk_id")):
            value = params.get(param)
            if value:
                queryset = queryset.filter(**{column: value}) if value.isdigit() else queryset.none()
        return _filters(queryset.order_by("-created_at", "-id"), params)
