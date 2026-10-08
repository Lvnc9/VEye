from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.pagination import DefaultPagination
from apps.organization.access import access_for

from . import services
from .access import is_top, visible_leave
from .models import LeaveStatus, LeaveType
from .serializers import LeaveCreateSerializer, LeaveRequestSerializer, NoteSerializer


class LeaveRequestViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """`/leave/requests/` — ask for days off, and decide on other people's.

    **`get_queryset()` decides visibility** (`visible_leave`): your own requests; those of people under the
    nodes you lead; everything for HR (`manage_personnel`) and the مدیر عامل. Filters: `?status=`,
    `?leave_type=`, `?mine=1` (only my own), `?to_decide=1` (pending requests of *other* people that I
    may decide), `?q=` (the requester's name). Newest first by start date. No edit, no delete: a request is
    approved, rejected or cancelled (`approve/`, `reject/` with a required note, `cancel/`)."""

    serializer_class = LeaveRequestSerializer
    pagination_class = DefaultPagination
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        queryset = visible_leave(self.request)
        if self.action != "list":
            return queryset
        params = self.request.query_params
        user = self.request.user
        for param, allowed in (("status", LeaveStatus.values), ("leave_type", LeaveType.values)):
            value = params.get(param)
            if value:
                queryset = queryset.filter(**{param: value}) if value in allowed else queryset.none()
        if params.get("mine") in ("1", "true"):
            queryset = queryset.filter(requester=user)
        if params.get("to_decide") in ("1", "true"):
            queryset = queryset.filter(status=LeaveStatus.PENDING).exclude(requester=user)
            if not is_top(user):
                queryset = queryset.filter(access_for(self.request).led_subtree_q("node__path"))
        if term := (params.get("q") or "").strip():
            queryset = queryset.filter(Q(requester__full_name__icontains=term))
        return queryset.order_by("-starts_on", "-id")

    def _one(self, leave):
        return LeaveRequestSerializer(visible_leave(self.request).get(pk=leave.pk), context=self.get_serializer_context()).data

    def create(self, request, *args, **kwargs):
        serializer = LeaveCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        leave = services.request_leave(actor=request.user, **serializer.validated_data)
        return Response(self._one(leave), status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        serializer = NoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(self._one(services.approve(self.get_object(), actor=request.user, note=serializer.validated_data["note"])))

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        serializer = NoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(self._one(services.reject(self.get_object(), actor=request.user, note=serializer.validated_data["note"])))

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return Response(self._one(services.cancel(self.get_object(), actor=request.user)))
