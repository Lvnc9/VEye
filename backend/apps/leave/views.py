from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Capability, User
from apps.core.pagination import DefaultPagination
from apps.core.permissions import HasCapability
from apps.organization.access import access_for

from . import services
from .access import is_top, visible_leave
from .models import Holiday, LeaveEntitlement, LeaveStatus, LeaveType
from .serializers import (
    EntitlementSerializer,
    HolidaySerializer,
    LeaveCreateSerializer,
    LeavePolicySerializer,
    LeaveRequestSerializer,
    NoteSerializer,
    SpanSerializer,
)
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
        balance = []
        if request.query_params.get("leave_type", LeaveType.ANNUAL) == LeaveType.ANNUAL:
            # Phase 22: what this span would leave of my annual balance, year by year.
            from .balances import Ledger, days_by_year

            ledger = Ledger(request.user)
            for year, days in sorted(days_by_year(start, end, ledger.holidays).items()):
                current = ledger.balance(year)
                if current is not None:
                    balance.append(
                        {"year": year, "requested": days, "remaining": current.remaining, "exceeds": days > current.remaining}
                    )
        return Response(
            {
                "starts_on": start,
                "ends_on": end,
                "calendar_days": (end - start).days + 1,
                "days": working_days(start, end, {h.date for h in holidays}),
                "holidays": HolidaySerializer(holidays, many=True).data,
                "balance": balance,
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


def _sees_balances_of_everyone(request) -> bool:
    return is_top(request.user) or access_for(request).holds(Capability.MANAGE_PERSONNEL)


def _may_see_balance(request, person) -> bool:
    """Your own; HR's and the مدیر عامل's for anyone; a مسئول's for the people placed beneath them."""
    if person.pk == request.user.pk or _sees_balances_of_everyone(request):
        return True
    from apps.organization.models import Membership

    org = access_for(request)
    return any(org.leads(m.node) for m in Membership.objects.filter(user=person, node__is_active=True).select_related("node"))


def _year_param(request) -> int:
    from .balances import current_year

    raw = request.query_params.get("year", "")
    return int(raw) if raw.isdigit() else current_year()


class BalanceView(APIView):
    """GET /leave/balance/?year=&user= — one person's annual-leave balance (Phase 22); mine by default."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .balances import Ledger
        from .models import LeavePolicy

        person = request.user
        if raw := request.query_params.get("user", ""):
            person = User.objects.filter(pk=raw).first() if raw.isdigit() else None
            if person is None or not _may_see_balance(request, person):
                raise NotFound("یافت نشد.")
        year = _year_param(request)
        policy = LeavePolicy.current()
        balance = Ledger(person, policy=policy).balance(year)
        return Response(
            {
                "user": {"id": person.pk, "full_name": person.full_name},
                "year": year,
                "tracked": balance is not None,
                "balance": balance.as_dict() if balance else None,
                "policy": {"annual_days": policy.annual_days, "carry_max": policy.carry_max, "start_year": policy.start_year},
            }
        )


class BalancesView(APIView):
    """GET /leave/balances/?year=&q= — everyone's annual-leave balance for HR and the مدیر عامل («مانده مرخصی»)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.organization.queries import search_people

        from .balances import Ledger
        from .models import LeavePolicy
        from .workdays import HolidayCache

        if not _sees_balances_of_everyone(request):
            raise PermissionDenied("فقط منابع انسانی و مدیر عامل ماندهٔ مرخصی همه را می‌بینند.")
        year = _year_param(request)
        people = search_people(User.objects.filter(is_active=True, is_developer=False), request.query_params.get("q", ""))
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(people.order_by("full_name", "id"), request, view=self)
        policy, holidays = LeavePolicy.current(), HolidayCache()
        rows = []
        for person in page:
            balance = Ledger(person, policy=policy, holidays=holidays).balance(year)
            rows.append(
                {
                    "user": {"id": person.pk, "full_name": person.full_name, "title": person.title},
                    "has_override": LeaveEntitlement.objects.filter(user=person, year=year).exists(),
                    "balance": balance.as_dict() if balance else None,
                }
            )
        return paginator.get_paginated_response(rows)


class EntitlementView(APIView):
    """PUT /leave/entitlements/ {user, year, days|null} — HR sets (or, with null, clears) one person's
    entitlement for a year: a different contract, or the opening balance in the start year."""

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = Capability.MANAGE_PERSONNEL

    def put(self, request):
        serializer = EntitlementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        person = User.objects.filter(pk=data["user"], is_developer=False).first()
        if person is None:
            raise NotFound("شخص یافت نشد.")
        if data["days"] is None:
            LeaveEntitlement.objects.filter(user=person, year=data["year"]).delete()
        else:
            LeaveEntitlement.objects.update_or_create(user=person, year=data["year"], defaults={"days": data["days"]})
        from .balances import Ledger

        balance = Ledger(person).balance(data["year"])
        return Response({"user": person.pk, "year": data["year"], "balance": balance.as_dict() if balance else None})


class PolicyView(APIView):
    """GET/PATCH /leave/policy/ — the annual-leave rule: anyone reads it, HR changes it."""

    permission_classes = [IsAuthenticated, HasCapability]
    write_capability = Capability.MANAGE_PERSONNEL

    def _payload(self, policy):
        return {"annual_days": policy.annual_days, "carry_max": policy.carry_max, "start_year": policy.start_year}

    def get(self, request):
        from .models import LeavePolicy

        return Response(self._payload(LeavePolicy.current()))

    def patch(self, request):
        from .models import LeavePolicy

        serializer = LeavePolicySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        policy = LeavePolicy.current()
        for field, value in serializer.validated_data.items():
            setattr(policy, field, value)
        policy.save()
        return Response(self._payload(policy))
