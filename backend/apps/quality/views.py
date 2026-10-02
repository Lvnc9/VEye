from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.pagination import DefaultPagination

from . import services
from .access import can_report, visible_nonconformances
from .models import NcSeverity, NcSource, NcStatus
from .serializers import (
    AcceptSerializer,
    NonConformanceCreateSerializer,
    NonConformanceSerializer,
    NonConformanceUpdateSerializer,
    ReasonSerializer,
)


class NonConformanceViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """`/quality/nonconformances/` — recorded problems.

    **`get_queryset()` is the only thing that decides visibility** (access.py): a record you may not
    read is a 404 and cannot leak through a list or an action route. Anyone signed in may report; the
    rest needs the record's manager (`manage_quality`, or leading its node or one above it).
    Filters: `?status= ?severity= ?source=`, `?node=<id>` (that node **and everything beneath it**),
    `?mine=reported|manage`, `?q=` (title, description, or a code like `NC-0042` / `42`).
    """

    serializer_class = NonConformanceSerializer
    pagination_class = DefaultPagination
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = visible_nonconformances(self.request)
        params = self.request.query_params
        if self.action != "list":
            return queryset
        for param, allowed in (("status", NcStatus.values), ("severity", NcSeverity.values), ("source", NcSource.values)):
            value = params.get(param)
            if value:
                queryset = queryset.filter(**{param: value}) if value in allowed else queryset.none()
        if node := params.get("node"):
            queryset = self._within_node(queryset, node)
        if params.get("mine") == "reported":
            queryset = queryset.filter(reported_by=self.request.user)
        if term := (params.get("q") or "").strip():
            queryset = queryset.filter(self._search(term))
        return queryset

    @staticmethod
    def _within_node(queryset, node: str):
        from apps.organization.models import OrgNode

        if not node.isdigit():
            return queryset.none()
        target = OrgNode.objects.filter(pk=node).first()
        return queryset.filter(owner_node__path__startswith=target.path) if target else queryset.none()

    @staticmethod
    def _search(term: str) -> Q:
        query = Q(title__icontains=term) | Q(description__icontains=term)
        digits = term.upper().removeprefix("NC-").lstrip("0")
        if digits.isdigit():
            query |= Q(pk=int(digits))
        return query

    def _one(self, nc):
        fresh = visible_nonconformances(self.request).get(pk=nc.pk)
        return NonConformanceSerializer(fresh, context=self.get_serializer_context()).data

    def create(self, request, *args, **kwargs):
        if not can_report(request.user):
            raise PermissionDenied("این حساب نمی‌تواند عدم‌انطباق ثبت کند.")
        serializer = NonConformanceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        nc = services.report(actor=request.user, **serializer.validated_data)
        return Response(self._one(nc), status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        nc = self.get_object()
        serializer = NonConformanceUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        nc = services.edit(nc, actor=request.user, changes=dict(serializer.validated_data))
        return Response(self._one(nc))

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        nc = self.get_object()
        serializer = AcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        nc = services.accept(nc, actor=request.user, **serializer.validated_data)
        return Response(self._one(nc))

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        nc = self.get_object()
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        nc = services.reject(nc, actor=request.user, reason=serializer.validated_data["reason"])
        return Response(self._one(nc))

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        nc = self.get_object()
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        nc = services.reopen(nc, actor=request.user, reason=serializer.validated_data["reason"])
        return Response(self._one(nc))
