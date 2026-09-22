from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.pagination import DefaultPagination
from apps.core.text import normalize_search_term

from . import services
from .access import CanManageProject, can_create_project, can_manage_project, visible_projects
from .models import Objective, ProjectMember
from .queries import overdue_q, with_progress
from .serializers import (
    MemberCreateSerializer,
    MemberUpdateSerializer,
    ObjectiveInputSerializer,
    ObjectiveSerializer,
    ObjectiveUpdateSerializer,
    ProjectCreateSerializer,
    ProjectDetailSerializer,
    ProjectMemberSerializer,
    ProjectSerializer,
    ProjectUpdateSerializer,
    ReorderSerializer,
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
        queryset = with_progress(visible_projects(self.request)).prefetch_related(
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
        if params.get("overdue") in ("1", "true") and self.action == "list":
            queryset = queryset.filter(overdue_count__gt=0)
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
            objectives=[dict(o) for o in data["objectives"]],
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

    # -- objectives ---------------------------------------------------------

    def _manager_only(self, request, project):
        if not can_manage_project(request, project):
            raise PermissionDenied("شما مدیر این پروژه نیستید.")

    def _objective_context(self, request, project):
        return {"request": request, "manage": can_manage_project(request, project)}

    def _member_for(self, project, user):
        try:
            return project.members.get(user=user)
        except ProjectMember.DoesNotExist:
            raise ValidationError({"assignee": ["مسئول ریزهدف باید یکی از اعضای پروژه باشد."]})

    @action(detail=True, methods=["get", "post"], url_path="objectives", permission_classes=[IsAuthenticated])
    def objectives(self, request, pk=None):
        """The plan. Anyone who can read the project reads it (`?status=`, `?assignee=<user id>|me`,
        `?overdue=1`); creating an objective needs the project's مدیر or a lead."""
        project = self.get_object()  # scoped: an invisible project is a 404
        context = self._objective_context(request, project)
        if request.method == "GET":
            rows = project.objectives.select_related("assignee__user")
            params = request.query_params
            if value := params.get("status"):
                rows = rows.filter(status=value)
            if value := params.get("assignee"):
                who = request.user.pk if value == "me" else (int(value) if value.isdigit() else None)
                rows = rows.filter(assignee__user_id=who) if who is not None else rows.none()
            if params.get("overdue") in ("1", "true"):
                rows = rows.filter(overdue_q())
            return Response(ObjectiveSerializer(rows, many=True, context=context).data)

        self._manager_only(request, project)
        serializer = ObjectiveInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        assignee = self._member_for(project, data.pop("assignee"))
        objective = services.add_objective(project, actor=request.user, assignee=assignee, **data)
        objective = Objective.objects.select_related("assignee__user").get(pk=objective.pk)
        return Response(ObjectiveSerializer(objective, context=context).data, status=status.HTTP_201_CREATED)

    @action(
        detail=True, methods=["patch", "delete"], url_path=r"objectives/(?P<objective_id>\d+)",
        permission_classes=[IsAuthenticated],
    )
    def objective(self, request, pk=None, objective_id=None):
        """Edit or remove one objective. Its assignee may change **its status** (an assignee who cannot
        mark their own work done is a dead feature); everything else — title, deadline, weight,
        reassigning, deleting — is for the project's مدیر or a lead."""
        project = self.get_object()
        try:
            objective = Objective.objects.select_related("assignee__user").get(pk=objective_id, project=project)
        except Objective.DoesNotExist:
            raise NotFound("ریزهدف یافت نشد.")
        context = self._objective_context(request, project)

        if request.method == "DELETE":
            self._manager_only(request, project)
            services.remove_objective(objective, actor=request.user)
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = ObjectiveUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        changes = dict(serializer.validated_data)
        only_status = set(changes) <= {"status"}
        if not (only_status and objective.assignee.user_id == request.user.pk):
            self._manager_only(request, project)
        if "assignee" in changes:
            changes["assignee"] = self._member_for(project, changes["assignee"])
        objective = services.update_objective(objective, actor=request.user, changes=changes)
        objective = Objective.objects.select_related("assignee__user").get(pk=objective.pk)
        return Response(ObjectiveSerializer(objective, context=context).data)

    @action(detail=True, methods=["post"], url_path="objectives/reorder", permission_classes=[IsAuthenticated])
    def reorder(self, request, pk=None):
        project = self.get_object()
        self._manager_only(request, project)
        serializer = ReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.reorder_objectives(project, actor=request.user, ordered_ids=serializer.validated_data["order"])
        rows = project.objectives.select_related("assignee__user")
        return Response(ObjectiveSerializer(rows, many=True, context=self._objective_context(request, project)).data)
