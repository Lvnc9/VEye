from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Exists, OuterRef, Prefetch
from django.http import FileResponse, Http404
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Capability
from apps.core.pagination import DefaultPagination
from apps.core.permissions import HasCapability

from . import memberships, queries, services, tree
from .models import Company, Membership, OrgNode
from .serializers import (
    CompanyUpdateSerializer,
    MembershipCreateSerializer,
    MembershipSerializer,
    MembershipUpdateSerializer,
    OrgNodeCreateSerializer,
    OrgNodeSerializer,
    OrgNodeUpdateSerializer,
    PersonSerializer,
    company_payload,
)

User = get_user_model()


def _flag(request, name: str) -> bool:
    return request.query_params.get(name) in ("1", "true")


def _members_of(queryset, request):
    """Membership rows, minus deactivated people unless `?include_inactive=1`. A deactivated
    person keeps their memberships (reactivating restores them); they just stop showing up."""
    queryset = queryset.select_related("user", "node")
    if not _flag(request, "include_inactive"):
        queryset = queryset.filter(user__is_active=True)
    return queryset.order_by("-is_lead", "user__full_name", "id")


class OrgNodeViewSet(viewsets.ModelViewSet):
    """`/org/nodes/` — the company's حوزه, واحد and بخش.

    Anyone signed in can read the chart (the personnel directory is already open to them,
    and hiding the chart from people who can already see everyone would be theatre).
    Writing needs `manage_organization`. Every write goes through `tree.py`, which owns the
    path/depth/parent-kind rules; the serializers only check the shape of the input.
    """

    queryset = OrgNode.objects.all()
    serializer_class = OrgNodeSerializer
    pagination_class = DefaultPagination
    permission_classes = [IsAuthenticated, HasCapability]
    write_capability = Capability.MANAGE_ORGANIZATION
    # No PUT: a node is renamed or moved with PATCH, and `kind` never changes.
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if kind := params.get("kind"):
            queryset = queryset.filter(kind=kind)
        if parent := params.get("parent"):
            queryset = queryset.filter(parent_id=parent) if parent.isdigit() else queryset.none()
        if (is_active := params.get("is_active")) in ("true", "1", "false", "0"):
            queryset = queryset.filter(is_active=is_active in ("true", "1"))
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = OrgNodeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        node = tree.create_node(
            kind=data["kind"], name=data["name"], parent=data["parent"], created_by=request.user
        )
        return Response(OrgNodeSerializer(node).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        node = self.get_object()
        serializer = OrgNodeUpdateSerializer(node, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        node = tree.update_node(node, name=data.get("name"), parent=data.get("parent"))
        return Response(OrgNodeSerializer(node).data)

    def destroy(self, request, *args, **kwargs):
        tree.delete_node(self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def members(self, request, pk=None):
        """The people directly in this node, leads first. (A بخش's picker; a lead's people below
        them are found by walking the tree, not by this endpoint.)"""
        node = self.get_object()
        queryset = _members_of(Membership.objects.filter(node=node), request)
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(MembershipSerializer(page, many=True).data)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        return Response(OrgNodeSerializer(tree.archive_node(self.get_object())).data)

    @action(detail=True, methods=["post"])
    def unarchive(self, request, pk=None):
        return Response(OrgNodeSerializer(tree.unarchive_node(self.get_object())).data)


class OrgTreeView(APIView):
    """`GET /org/tree/` — the whole chart in one flat list, already in pre-order
    depth-first order (`ORDER BY path`), so the client only has to nest it. One query,
    whatever the tree's size.

    Over `ORG_TREE_MAX_NODES` it returns just the top two levels with `"truncated": true`;
    `?parent=<id>` then returns one node's direct children, a branch at a time.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if (parent := request.query_params.get("parent")) is not None:
            if not parent.isdigit():
                raise ValidationError({"parent": ["شناسهٔ گره معتبر نیست."]})
            if not OrgNode.objects.filter(pk=parent).exists():
                raise NotFound("گره یافت نشد.")
            nodes = OrgNode.objects.filter(parent_id=parent).order_by("path")
            return Response({"truncated": False, "nodes": OrgNodeSerializer(nodes, many=True).data})

        limit = settings.ORG_TREE_MAX_NODES
        nodes = list(OrgNode.objects.order_by("path")[: limit + 1])
        truncated = len(nodes) > limit
        if truncated:
            nodes = list(OrgNode.objects.filter(depth__lte=1).order_by("path"))
        return Response({"truncated": truncated, "nodes": OrgNodeSerializer(nodes, many=True).data})


def _get_company() -> Company:
    company = Company.objects.select_related("root").first()
    if company is None:
        raise NotFound("شرکت هنوز راه‌اندازی نشده است.")
    return company


class CompanyView(APIView):
    """`/org/company/` — the profile. Read by anyone signed in, edited with
    `manage_organization`. The name shown here is the root node's."""

    permission_classes = [IsAuthenticated, HasCapability]
    write_capability = Capability.MANAGE_ORGANIZATION

    def get(self, request):
        return Response(company_payload(_get_company(), request))

    def patch(self, request):
        company = _get_company()
        serializer = CompanyUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        company = services.update_company(company, **serializer.validated_data)
        return Response(company_payload(company, request))


class CompanyLogoView(APIView):
    permission_classes = [IsAuthenticated, HasCapability]
    write_capability = Capability.MANAGE_ORGANIZATION
    parser_classes = [MultiPartParser]

    def get(self, request):
        company = _get_company()
        if not company.logo:
            raise Http404
        try:
            handle = company.logo.open("rb")
        except FileNotFoundError:
            raise Http404
        response = FileResponse(handle, content_type="image/png")
        response["Cache-Control"] = "private, max-age=3600"
        return response

    def post(self, request):
        upload = request.FILES.get("logo")
        if upload is None:
            raise ValidationError({"logo": ["تصویری ارسال نشده است."]})
        company = services.set_logo(_get_company(), upload=upload)
        return Response(company_payload(company, request))

    def delete(self, request):
        company = services.remove_logo(_get_company())
        return Response(company_payload(company, request))


class MembershipViewSet(viewsets.ModelViewSet):
    """`/org/memberships/` — who sits where. Readable by anyone signed in; writing needs
    `manage_membership`. Filters: `?node=`, `?user=`, `?is_lead=1`, `?include_inactive=1`.

    A membership's person and node never change; PATCH edits `is_lead`, `is_primary` and
    `position_label`. See memberships.py for the "exactly one primary" rule."""

    queryset = Membership.objects.all()
    serializer_class = MembershipSerializer
    pagination_class = DefaultPagination
    permission_classes = [IsAuthenticated, HasCapability]
    write_capability = Capability.MANAGE_MEMBERSHIP
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        for field in ("node", "user"):
            if value := params.get(field):
                queryset = queryset.filter(**{f"{field}_id": value}) if value.isdigit() else queryset.none()
        if _flag(self.request, "is_lead"):
            queryset = queryset.filter(is_lead=True)
        if self.action == "list":
            return _members_of(queryset, self.request)
        return queryset.select_related("user", "node")

    def create(self, request, *args, **kwargs):
        serializer = MembershipCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        membership = memberships.add_membership(
            user=data["user"],
            node=data["node"],
            is_lead=data["is_lead"],
            is_primary=data["is_primary"],
            position_label=data["position_label"],
            added_by=request.user,
        )
        return Response(self._payload(membership), status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        membership = self.get_object()
        serializer = MembershipUpdateSerializer(membership, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        membership = memberships.update_membership(
            membership,
            is_lead=data.get("is_lead"),
            is_primary=data.get("is_primary"),
            position_label=data.get("position_label"),
        )
        return Response(self._payload(membership))

    def destroy(self, request, *args, **kwargs):
        memberships.remove_membership(self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _payload(self, membership):
        fresh = Membership.objects.select_related("user", "node").get(pk=membership.pk)
        return MembershipSerializer(fresh).data


class PeopleView(generics.ListAPIView):
    """`GET /org/people/` — people with where they sit, for the member picker and the chart's
    search. Any signed-in user. Deactivated people are hidden unless `?include_inactive=1`.

    Filters: `?q=` (name; Arabic/Persian letters and digits are treated alike), `?node=<id>`
    (people directly in that node), `?unassigned=1` (people with no membership yet — the
    setup wizard's and personnel screen's "who still needs a place")."""

    serializer_class = PersonSerializer
    pagination_class = DefaultPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        params = self.request.query_params
        queryset = User.objects.all()
        if not _flag(self.request, "include_inactive"):
            queryset = queryset.filter(is_active=True)
        if node := params.get("node"):
            queryset = (
                queryset.filter(memberships__node_id=node).distinct() if node.isdigit() else queryset.none()
            )
        if _flag(self.request, "unassigned"):
            queryset = queryset.filter(~Exists(Membership.objects.filter(user=OuterRef("pk"))))
        queryset = queries.search_people(queryset, params.get("q", ""))
        placed = Membership.objects.select_related("node").order_by("-is_primary", "node__path")
        return queryset.prefetch_related(Prefetch("memberships", queryset=placed)).order_by("full_name", "id")
