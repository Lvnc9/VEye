from django.db.models import Exists, OuterRef, Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import Capability
from apps.core.pagination import DefaultPagination
from apps.organization.access import access_for

from . import services
from .access import can_manage, can_report, visible_audits, visible_nonconformances
from .models import AuditStatus, CorrectiveAction, NcSeverity, NcSource, NcStatus, NonConformance
from .queries import with_action_counts, with_finding_counts
from .serializers import (
    AcceptSerializer,
    ActionCreateSerializer,
    ActionUpdateSerializer,
    AuditCompleteSerializer,
    AuditCreateSerializer,
    AuditSerializer,
    AuditUpdateSerializer,
    CloseSerializer,
    CorrectiveActionSerializer,
    FindingCreateSerializer,
    NonConformanceCreateSerializer,
    NonConformanceSerializer,
    NonConformanceUpdateSerializer,
    ReasonSerializer,
    VerifySerializer,
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
    `?audit=<id>` (the findings of one audit), `?mine=reported|assigned|manage`,
    `?overdue=1` (has an action past its deadline), `?q=` (title, description, or a code like
    `NC-0042` / `42`).

    Corrective actions live under `…/{id}/actions/`; the record's own transitions are `accept`,
    `reject`, `close` and `reopen`. Every row carries the derived `actions_*` counts and the `can_*`
    flags the buttons need.
    """

    serializer_class = NonConformanceSerializer
    pagination_class = DefaultPagination
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def _visible(self):
        return with_action_counts(visible_nonconformances(self.request))

    def get_queryset(self):
        queryset = self._visible()
        params = self.request.query_params
        if self.action != "list":
            return queryset
        for param, allowed in (("status", NcStatus.values), ("severity", NcSeverity.values), ("source", NcSource.values)):
            value = params.get(param)
            if value:
                queryset = queryset.filter(**{param: value}) if value in allowed else queryset.none()
        if node := params.get("node"):
            queryset = self._within_node(queryset, node)
        if audit := params.get("audit"):
            queryset = queryset.filter(audit_id=audit) if audit.isdigit() else queryset.none()
        mine = params.get("mine")
        if mine == "reported":
            queryset = queryset.filter(reported_by=self.request.user)
        elif mine == "assigned":
            queryset = queryset.filter(
                Exists(CorrectiveAction.objects.filter(nc=OuterRef("pk"), assignee=self.request.user))
            )
        elif mine == "manage":
            org = access_for(self.request)
            if not org.holds(Capability.MANAGE_QUALITY):
                queryset = queryset.filter(org.led_subtree_q("owner_node__path"))
        if params.get("overdue") in ("1", "true"):
            queryset = queryset.filter(status=NcStatus.IN_PROGRESS, actions_overdue__gt=0)
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
        fresh = self._visible().get(pk=nc.pk)
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

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        nc = self.get_object()
        serializer = CloseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        nc = services.close(nc, actor=request.user, effectiveness_note=serializer.validated_data["effectiveness_note"])
        return Response(self._one(nc))

    # -- corrective actions ------------------------------------------------------

    def _action_context(self, nc):
        return {
            "request": self.request,
            "nc": nc,
            "manager": can_manage(access_for(self.request), nc.owner_node),
        }

    def _action_payload(self, nc, action):
        """One action as the panel shows it, with flags judged against the record *as it is now*."""
        nc = NonConformance.objects.select_related("owner_node").get(pk=nc.pk)
        action = CorrectiveAction.objects.select_related("assignee", "verified_by").get(pk=action.pk)
        return CorrectiveActionSerializer(action, context=self._action_context(nc)).data

    def _fetch_action(self, nc, action_id) -> CorrectiveAction:
        try:
            return CorrectiveAction.objects.select_related("assignee", "verified_by").get(pk=action_id, nc=nc)
        except CorrectiveAction.DoesNotExist:
            raise NotFound("اقدام یافت نشد.")

    @action(detail=True, methods=["get", "post"], url_path="actions", url_name="actions")
    def actions(self, request, pk=None):
        """GET the record's corrective actions (every one, cancelled included, soonest deadline first);
        POST adds one — a manager's act, only while the record is «در دست اقدام»."""
        nc = self.get_object()
        if request.method == "GET":
            rows = CorrectiveAction.objects.filter(nc=nc).select_related("assignee", "verified_by")
            return Response(CorrectiveActionSerializer(rows, many=True, context=self._action_context(nc)).data)
        serializer = ActionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        created = services.add_action(nc, actor=request.user, **serializer.validated_data)
        return Response(self._action_payload(nc, created), status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path=r"actions/(?P<action_id>\d+)", url_name="action-detail")
    def action_detail(self, request, pk=None, action_id=None):
        nc = self.get_object()
        target = self._fetch_action(nc, action_id)
        serializer = ActionUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = services.update_action(nc, target, actor=request.user, changes=dict(serializer.validated_data))
        return Response(self._action_payload(nc, updated))

    @action(detail=True, methods=["post"], url_path=r"actions/(?P<action_id>\d+)/verify", url_name="action-verify")
    def action_verify(self, request, pk=None, action_id=None):
        nc = self.get_object()
        target = self._fetch_action(nc, action_id)
        serializer = VerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        done = services.verify_action(nc, target, actor=request.user, note=serializer.validated_data["note"])
        return Response(self._action_payload(nc, done))

    @action(
        detail=True, methods=["post"], url_path=r"actions/(?P<action_id>\d+)/fail-verification",
        url_name="action-fail-verification",
    )
    def action_fail_verification(self, request, pk=None, action_id=None):
        nc = self.get_object()
        target = self._fetch_action(nc, action_id)
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sent_back = services.fail_verification(nc, target, actor=request.user, reason=serializer.validated_data["reason"])
        return Response(self._action_payload(nc, sent_back))

    @action(detail=True, methods=["post"], url_path=r"actions/(?P<action_id>\d+)/cancel", url_name="action-cancel")
    def action_cancel(self, request, pk=None, action_id=None):
        nc = self.get_object()
        target = self._fetch_action(nc, action_id)
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dropped = services.cancel_action(nc, target, actor=request.user, reason=serializer.validated_data["reason"])
        return Response(self._action_payload(nc, dropped))



class AuditViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """`/quality/audits/` — planned checks of one part of the chart.

    As for records, **`get_queryset()` decides visibility** (`visible_audits`): an audit you may not
    read is a 404 everywhere. Only `manage_quality` plans, edits and cancels; the lead auditor (or
    `manage_quality`) starts, completes and raises findings. A finding is a non-conformance, so it is
    created here (`…/{id}/findings/`) but listed and worked on under `/quality/nonconformances/`
    (`?audit=<id>` gives an audit's findings).
    Filters: `?status=`, `?node=<id>` (audits of that node **and everything beneath it**),
    `?mine=auditor|manage`, `?q=` (title, or a code like `AU-0007` / `7`).
    """

    serializer_class = AuditSerializer
    pagination_class = DefaultPagination
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def _visible(self):
        return with_finding_counts(visible_audits(self.request))

    def get_queryset(self):
        queryset = self._visible()
        params = self.request.query_params
        if self.action != "list":
            return queryset
        value = params.get("status")
        if value:
            queryset = queryset.filter(status=value) if value in AuditStatus.values else queryset.none()
        if node := params.get("node"):
            from apps.organization.models import OrgNode

            target = OrgNode.objects.filter(pk=node).first() if node.isdigit() else None
            queryset = queryset.filter(scope_node__path__startswith=target.path) if target else queryset.none()
        mine = params.get("mine")
        if mine == "auditor":
            queryset = queryset.filter(lead_auditor=self.request.user)
        elif mine == "manage":
            org = access_for(self.request)
            if not org.holds(Capability.MANAGE_QUALITY):
                queryset = queryset.filter(org.led_subtree_q("scope_node__path"))
        if term := (params.get("q") or "").strip():
            query = Q(title__icontains=term)
            digits = term.upper().removeprefix("AU-").lstrip("0")
            if digits.isdigit():
                query |= Q(pk=int(digits))
            queryset = queryset.filter(query)
        return queryset

    def _one(self, audit):
        return AuditSerializer(self._visible().get(pk=audit.pk), context=self.get_serializer_context()).data

    def create(self, request, *args, **kwargs):
        serializer = AuditCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        audit = services.plan_audit(actor=request.user, **serializer.validated_data)
        return Response(self._one(audit), status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        audit = self.get_object()
        serializer = AuditUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        audit = services.edit_audit(audit, actor=request.user, changes=dict(serializer.validated_data))
        return Response(self._one(audit))

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        audit = services.start_audit(self.get_object(), actor=request.user)
        return Response(self._one(audit))

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        audit = self.get_object()
        serializer = AuditCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        audit = services.complete_audit(audit, actor=request.user, summary=serializer.validated_data["summary"])
        return Response(self._one(audit))

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        audit = self.get_object()
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        audit = services.cancel_audit(audit, actor=request.user, reason=serializer.validated_data["reason"])
        return Response(self._one(audit))

    @action(detail=True, methods=["post"])
    def findings(self, request, pk=None):
        """Raise a finding — creates a non-conformance (source AUDIT) and answers with it, as the
        record's own endpoints do."""
        audit = self.get_object()
        serializer = FindingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        nc = services.raise_finding(audit, actor=request.user, **serializer.validated_data)
        fresh = with_action_counts(visible_nonconformances(request)).get(pk=nc.pk)
        return Response(
            NonConformanceSerializer(fresh, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )
