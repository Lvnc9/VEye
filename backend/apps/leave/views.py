from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import Capability, User
from apps.core.pagination import DefaultPagination
from apps.core.permissions import HasCapability
from apps.organization.access import access_for

from . import services
from .access import is_top, visible_leave
from .models import Holiday, LeaveStatus, LeaveType
from .serializers import HolidaySerializer, LeaveCreateSerializer, LeaveRequestSerializer, NoteSerializer, SpanSerializer
from .workdays import jalali_year_bounds, working_days


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
            # Phase 22: names are stored as typed (Arabic ي/ك too), so compare them normalised.
            from apps.organization.queries import search_people

            queryset = queryset.filter(requester__in=search_people(User.objects.all(), term))
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

    @action(detail=False, methods=["get"])
    def preview(self, request):
        """What a span would count before it is asked for (Phase 22): working days, calendar days and the
        holidays inside it — so the form never re-implements the holiday rule."""
        serializer = SpanSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        start, end = serializer.validated_data["starts_on"], serializer.validated_data["ends_on"]
        holidays = Holiday.objects.filter(date__range=(start, end))
        return Response(
            {
                "starts_on": start,
                "ends_on": end,
                "calendar_days": (end - start).days + 1,
                "days": working_days(start, end, {h.date for h in holidays}),
                "holidays": HolidaySerializer(holidays, many=True).data,
            }
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return Response(self._one(services.cancel(self.get_object(), actor=request.user)))


class HolidayViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """`/leave/holidays/` (Phase 22): the official holidays a day of leave does not count on. Anyone signed in
    reads them (the leave form and the calendar show them); HR (`manage_personnel`) adds and removes them.
    `?year=1405` narrows to a Jalali year."""

    serializer_class = HolidaySerializer
    permission_classes = [IsAuthenticated, HasCapability]
    write_capability = Capability.MANAGE_PERSONNEL
    pagination_class = None

    def get_queryset(self):
        queryset = Holiday.objects.all()
        year = self.request.query_params.get("year", "")
        if year:
            if not year.isdigit():
                return queryset.none()
            first, last = jalali_year_bounds(int(year))
            queryset = queryset.filter(date__range=(first, last))
        return queryset

    def perform_create(self, serializer):
        from django.db import IntegrityError, transaction

        from apps.core.exceptions import ConflictError

        try:
            with transaction.atomic():
                serializer.save()
        except IntegrityError:
            raise ConflictError("برای این روز تعطیلی ثبت شده است.", code="holiday_exists")
