from django.conf import settings
from django.http import FileResponse, Http404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Capability
from apps.core.pagination import DefaultPagination
from apps.core.permissions import HasCapability

from . import services, tree
from .models import Company, OrgNode
from .serializers import (
    CompanyUpdateSerializer,
    OrgNodeCreateSerializer,
    OrgNodeSerializer,
    OrgNodeUpdateSerializer,
    company_payload,
)


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
