from django.db.models import Prefetch
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.pagination import DefaultPagination
from apps.core.text import normalize_search_term

from . import services
from .access import CanManageProject, can_create_project, visible_projects
from .models import ProjectMember
from .serializers import (
    MemberCreateSerializer,
    MemberUpdateSerializer,
    ProjectCreateSerializer,
    ProjectDetailSerializer,
    ProjectMemberSerializer,
    ProjectSerializer,
    ProjectUpdateSerializer,
)


class ProjectViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """`/projects/` — planned work owned by a بخش.

    **`get_queryset()` is the only thing that decides visibility** (access.py): a project you may
    not read is a 404 and cannot leak through a list route. Writes need the project's مدیر or a
    lead of its بخش (or an ancestor); creating needs `create_project` or leading the target بخش.
    Filters: `?section=`, `?status=`, `?q=`, `?mine=1`, `?archived=1` (archived are hidden by default).
    """

    serializer_class = ProjectSerializer
    pagination_class = DefaultPagination
    permission_classes = [IsAuthenticated, CanManageProject]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = visible_projects(self.request).prefetch_related(
            Prefetch("members", queryset=ProjectMember.objects.select_related("user"))
        )
        params = self.request.query_params
        if self.action == "list":
            if params.get("archived") in ("1", "true"):
                queryset = queryset.filter(archived_at__isnull=False)
            else:
                queryset = queryset.filter(archived_at__isnull=True)
        if (section := params.get("section")) and self.action == "list":
            queryset = queryset.filter(section_id=section) if section.isdigit() else queryset.none()
        if (status_ := params.get("status")) and self.action == "list":
            queryset = queryset.filter(status=status_)
        if params.get("mine") in ("1", "true") and self.action == "list":
            queryset = queryset.filter(my_role__isnull=False)
        if (term := normalize_search_term(params.get("q", ""))) and self.action == "list":
            queryset = queryset.filter(name_key__icontains=term)
        return queryset

    def get_serializer_class(self):
        return ProjectDetailSerializer if self.action == "retrieve" else ProjectSerializer

    def _detail(self, project):
        fresh = self.get_queryset().get(pk=project.pk)
        return ProjectDetailSerializer(fresh, context=self.get_serializer_context()).data

    def create(self, request, *args, **kwargs):
        serializer = ProjectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if not can_create_project(request, data["section"]):
            raise PermissionDenied("شما اجازهٔ ایجاد پروژه در این بخش را ندارید.")
        project = services.create_project(
            actor=request.user,
            section=data["section"],
            name=data["name"],
            goal=data["goal"],
            starts_on=data["starts_on"],
            due_on=data["due_on"],
            members=[{"user": m["user"], "role": m["role"]} for m in data["members"]],
        )
        return Response(self._detail(project), status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        project = self.get_object()
        serializer = ProjectUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        project = services.update_project(project, actor=request.user, changes=dict(serializer.validated_data))
        return Response(self._detail(project))

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        project = services.archive_project(self.get_object(), actor=request.user)
        return Response(self._detail(project))

    @action(detail=True, methods=["post"])
    def unarchive(self, request, pk=None):
        project = services.unarchive_project(self.get_object(), actor=request.user)
        return Response(self._detail(project))

    @action(detail=True, methods=["post"], url_path="members")
    def add_member(self, request, pk=None):
        project = self.get_object()
        serializer = MemberCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member = services.add_member(
            project, actor=request.user, user=serializer.validated_data["user"], role=serializer.validated_data["role"]
        )
        member = ProjectMember.objects.select_related("user").get(pk=member.pk)
        return Response(ProjectMemberSerializer(member).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch", "delete"], url_path=r"members/(?P<member_id>\d+)")
    def member(self, request, pk=None, member_id=None):
        project = self.get_object()
        try:
            member = ProjectMember.objects.select_related("user").get(pk=member_id, project=project)
        except ProjectMember.DoesNotExist:
            raise NotFound("عضو یافت نشد.")
        if request.method == "DELETE":
            services.remove_member(member, actor=request.user)
            return Response(status=status.HTTP_204_NO_CONTENT)
        serializer = MemberUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member = services.change_role(member, actor=request.user, role=serializer.validated_data["role"])
        return Response(ProjectMemberSerializer(member).data)
