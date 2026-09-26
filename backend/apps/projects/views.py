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
from .access import CanManageProject, can_create_project, can_manage_meetings, can_manage_project, visible_projects
from .models import (
    MeetingAttendee,
    Objective,
    ObjectiveAssignee,
    ObjectiveUpdate,
    ProjectComment,
    ProjectDocumentLink,
    ProjectMeeting,
    ProjectMember,
)
from .queries import overdue_q, with_latest_update, with_progress
from .serializers import (
    CommentCreateSerializer,
    DocumentLinkCreateSerializer,
    MeetingInputSerializer,
    MeetingSerializer,
    MeetingUpdateSerializer,
    MemberCreateSerializer,
    MemberUpdateSerializer,
    ObjectiveInputSerializer,
    ObjectiveProgressBodySerializer,
    ObjectiveProgressSerializer,
    ObjectiveSerializer,
    ObjectiveUpdateSerializer,
    ProjectCommentSerializer,
    ProjectCreateSerializer,
    ProjectDetailSerializer,
    ProjectDocumentLinkSerializer,
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
        return {
            "request": request, "manage": can_manage_project(request, project), "archived": project.is_archived,
        }

    def _member_for(self, project, user):
        try:
            return project.members.get(user=user)
        except ProjectMember.DoesNotExist:
            raise ValidationError({"assignees": ["مسئول ریزهدف باید یکی از اعضای پروژه باشد."]})

    def _members_for(self, project, users):
        return [self._member_for(project, user) for user in users]

    @staticmethod
    def _with_assignees(queryset):
        return queryset.prefetch_related(
            Prefetch(
                "assignees",
                queryset=with_latest_update(ObjectiveAssignee.objects.select_related("member__user")),
            )
        )

    def _fetch_objective(self, project, objective_id):
        try:
            return self._with_assignees(Objective.objects).get(pk=objective_id, project=project)
        except Objective.DoesNotExist:
            raise NotFound("ریزهدف یافت نشد.")

    def _is_assignee(self, objective, user) -> bool:
        return any(a.member.user_id == user.pk for a in objective.assignees.all())

    @action(detail=True, methods=["get", "post"], url_path="objectives", permission_classes=[IsAuthenticated])
    def objectives(self, request, pk=None):
        """The plan. Anyone who can read the project reads it (`?status=`, `?assignee=<user id>|me`,
        `?overdue=1`); creating an objective needs the project's مدیر or a lead."""
        project = self.get_object()  # scoped: an invisible project is a 404
        context = self._objective_context(request, project)
        if request.method == "GET":
            rows = self._with_assignees(project.objectives)
            params = request.query_params
            if value := params.get("status"):
                rows = rows.filter(status=value)
            if value := params.get("assignee"):
                who = request.user.pk if value == "me" else (int(value) if value.isdigit() else None)
                rows = rows.filter(assignees__member__user_id=who) if who is not None else rows.none()
            if params.get("overdue") in ("1", "true"):
                rows = rows.filter(overdue_q())
            return Response(ObjectiveSerializer(rows, many=True, context=context).data)

        self._manager_only(request, project)
        serializer = ObjectiveInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        assignees = self._members_for(project, data.pop("assignees"))
        objective = services.add_objective(project, actor=request.user, assignees=assignees, **data)
        objective = self._fetch_objective(project, objective.pk)
        return Response(ObjectiveSerializer(objective, context=context).data, status=status.HTTP_201_CREATED)

    @action(
        detail=True, methods=["patch", "delete"], url_path=r"objectives/(?P<objective_id>\d+)",
        permission_classes=[IsAuthenticated],
    )
    def objective(self, request, pk=None, objective_id=None):
        """Edit or remove one objective. Any current assignee may change **its status** (an assignee
        who cannot mark their own work done is a dead feature); everything else — title, deadline,
        weight, the assignee set, deleting — is for the project's مدیر or a lead."""
        project = self.get_object()
        objective = self._fetch_objective(project, objective_id)
        context = self._objective_context(request, project)

        if request.method == "DELETE":
            self._manager_only(request, project)
            services.remove_objective(objective, actor=request.user)
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = ObjectiveUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        changes = dict(serializer.validated_data)
        only_status = set(changes) <= {"status"}
        if not (only_status and self._is_assignee(objective, request.user)):
            self._manager_only(request, project)
        if "assignees" in changes:
            changes["assignees"] = self._members_for(project, changes["assignees"])
        objective = services.update_objective(objective, actor=request.user, changes=changes)
        objective = self._fetch_objective(project, objective.pk)
        return Response(ObjectiveSerializer(objective, context=context).data)

    @action(detail=True, methods=["post"], url_path="objectives/reorder", permission_classes=[IsAuthenticated])
    def reorder(self, request, pk=None):
        project = self.get_object()
        self._manager_only(request, project)
        serializer = ReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.reorder_objectives(project, actor=request.user, ordered_ids=serializer.validated_data["order"])
        rows = self._with_assignees(project.objectives)
        return Response(ObjectiveSerializer(rows, many=True, context=self._objective_context(request, project)).data)

    # -- progress log ---------------------------------------------------------

    def _fetch_progress_update(self, objective, update_id):
        try:
            return ObjectiveUpdate.objects.select_related("author").get(pk=update_id, objective=objective)
        except ObjectiveUpdate.DoesNotExist:
            raise NotFound("گزارش پیشرفت یافت نشد.")

    def _my_latest_update_id(self, objective, user):
        return (
            objective.updates.filter(author=user).order_by("-created_at", "-id").values_list("id", flat=True).first()
        )

    @action(
        detail=True, methods=["get", "post"], url_path=r"objectives/(?P<objective_id>\d+)/updates",
        permission_classes=[IsAuthenticated],
    )
    def objective_updates(self, request, pk=None, objective_id=None):
        """The dated progress log under one objective (`?author=<uid>`, paginated, newest first).
        Anyone who can read the project reads it; only a *current* assignee may post."""
        project = self.get_object()
        objective = self._fetch_objective(project, objective_id)

        if request.method == "GET":
            rows = objective.updates.select_related("author").order_by("-created_at", "-id")
            if value := request.query_params.get("author"):
                who = int(value) if value.isdigit() else None
                rows = rows.filter(author_id=who) if who is not None else rows.none()
            page = self.paginate_queryset(rows)
            context = {"request": request, "my_latest_id": self._my_latest_update_id(objective, request.user)}
            return self.get_paginated_response(ObjectiveProgressSerializer(page, many=True, context=context).data)

        if not self._is_assignee(objective, request.user):
            raise PermissionDenied("فقط مسئولان این ریزهدف می‌توانند گزارش پیشرفت ثبت کنند.")
        serializer = ObjectiveProgressBodySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        update = services.add_objective_update(objective, actor=request.user, body=serializer.validated_data["body"])
        update = self._fetch_progress_update(objective, update.pk)
        context = {"request": request, "my_latest_id": update.pk}
        return Response(ObjectiveProgressSerializer(update, context=context).data, status=status.HTTP_201_CREATED)

    @action(
        detail=True, methods=["patch"], url_path=r"objectives/(?P<objective_id>\d+)/updates/(?P<update_id>\d+)",
        permission_classes=[IsAuthenticated],
    )
    def objective_update_entry(self, request, pk=None, objective_id=None, update_id=None):
        """Edit one's own **latest** entry on this objective. `services.edit_objective_update`
        re-checks "latest" under the project's row lock (two concurrent posts by the same author
        must not both think an older row is still current); authorship is checked here, the same
        split every other author-scoped write in this app follows (e.g. `comment`, below)."""
        project = self.get_object()
        objective = self._fetch_objective(project, objective_id)
        update = self._fetch_progress_update(objective, update_id)
        if update.author_id != request.user.pk:
            raise PermissionDenied("فقط نویسندهٔ گزارش می‌تواند آن را ویرایش کند.")
        serializer = ObjectiveProgressBodySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        update = services.edit_objective_update(update, actor=request.user, body=serializer.validated_data["body"])
        update = self._fetch_progress_update(objective, update.pk)
        context = {"request": request, "my_latest_id": update.pk}
        return Response(ObjectiveProgressSerializer(update, context=context).data)

    # -- comments -------------------------------------------------------------

    @action(detail=True, methods=["get", "post"], url_path="comments", permission_classes=[IsAuthenticated])
    def comments(self, request, pk=None):
        """The project's discussion (or, with `objective`, one ریز هدف's own). Anyone who can read
        the project may read and post — a feed with no human note is a machine log. Only a comment's
        own author may ever delete it (see `comment` below); paginated, since a long-lived project
        can accumulate many, unlike its (capped) objectives."""
        project = self.get_object()
        if request.method == "GET":
            rows = project.comments.select_related("author", "objective").order_by("-created_at", "-id")
            page = self.paginate_queryset(rows)
            return self.get_paginated_response(
                ProjectCommentSerializer(page, many=True, context=self.get_serializer_context()).data
            )
        serializer = CommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = services.add_comment(
            project, actor=request.user, body=serializer.validated_data["body"],
            objective=serializer.validated_data["objective"],
        )
        comment = ProjectComment.objects.select_related("author", "objective").get(pk=comment.pk)
        return Response(
            ProjectCommentSerializer(comment, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True, methods=["delete"], url_path=r"comments/(?P<comment_id>\d+)",
        permission_classes=[IsAuthenticated],
    )
    def comment(self, request, pk=None, comment_id=None):
        """Delete a comment — the author only, no exception: not the project's مدیر, not مدیر عامل.
        The same "sender only" rule the chat design states for messages (docs/11 §2.6)."""
        project = self.get_object()
        try:
            comment = ProjectComment.objects.get(pk=comment_id, project=project)
        except ProjectComment.DoesNotExist:
            raise NotFound("یادداشت یافت نشد.")
        if comment.author_id != request.user.pk:
            raise PermissionDenied("فقط نویسندهٔ یادداشت می‌تواند آن را حذف کند.")
        services.remove_comment(comment, actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # -- linked documents -------------------------------------------------------------

    @action(detail=True, methods=["get", "post"], url_path="documents", permission_classes=[IsAuthenticated])
    def documents(self, request, pk=None):
        """The documents this project produced or relies on. Anyone who can read the project may
        read the list; linking (and unlinking) needs the project's مدیر or a lead, the same as any
        other edit to the project's own content."""
        project = self.get_object()
        if request.method == "GET":
            rows = project.document_links.select_related("document", "linked_by")
            return Response(
                ProjectDocumentLinkSerializer(rows, many=True, context=self.get_serializer_context()).data
            )
        self._manager_only(request, project)
        serializer = DocumentLinkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        link = services.link_document(
            project, actor=request.user, document=serializer.validated_data["document"],
            caption=serializer.validated_data["caption"],
        )
        link = ProjectDocumentLink.objects.select_related("document", "linked_by").get(pk=link.pk)
        return Response(
            ProjectDocumentLinkSerializer(link, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True, methods=["delete"], url_path=r"documents/(?P<link_id>\d+)",
        permission_classes=[IsAuthenticated],
    )
    def document_link(self, request, pk=None, link_id=None):
        project = self.get_object()
        self._manager_only(request, project)
        try:
            link = ProjectDocumentLink.objects.get(pk=link_id, project=project)
        except ProjectDocumentLink.DoesNotExist:
            raise NotFound("پیوند مستند یافت نشد.")
        services.unlink_document(link, actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # -- meetings -------------------------------------------------------------

    #: «جدول جلسات» is one unpaginated list (the contract); a project past this many meetings shows
    #: the newest.
    MEETINGS_LIST_LIMIT = 200

    def _meeting_context(self, request, project):
        return {"request": request, "manage": can_manage_meetings(request, project), "archived": project.is_archived}

    @staticmethod
    def _with_attendees(queryset):
        return queryset.prefetch_related(
            Prefetch("attendees", queryset=MeetingAttendee.objects.select_related("member__user"))
        )

    def _fetch_meeting(self, project, meeting_id):
        try:
            return self._with_attendees(ProjectMeeting.objects).get(pk=meeting_id, project=project)
        except ProjectMeeting.DoesNotExist:
            raise NotFound("جلسه یافت نشد.")

    def _meetings_manager_only(self, request, project):
        if not can_manage_meetings(request, project):
            if project.is_archived:
                services.require_writable(project)  # the archived 409 says why better than a 403
            raise PermissionDenied("فقط مدیر پروژه می‌تواند جلسه تعیین یا ویرایش کند.")

    def _attendee_members(self, project, users):
        members = {m.user_id: m for m in project.members.filter(user__in=users)}
        missing = [u for u in users if u.pk not in members]
        if missing:
            raise ValidationError({"attendees": ["شرکت‌کنندگان باید از اعضای همین پروژه باشند."]})
        return [members[u.pk] for u in users]

    @action(detail=True, methods=["get", "post"], url_path="meetings", permission_classes=[IsAuthenticated])
    def meetings(self, request, pk=None):
        """Every reader of the project sees every meeting (newest first, unpaginated, at most
        `MEETINGS_LIST_LIMIT`); scheduling one needs `can_manage_meetings`."""
        project = self.get_object()
        context = self._meeting_context(request, project)
        if request.method == "GET":
            rows = self._with_attendees(project.meetings.all())[: self.MEETINGS_LIST_LIMIT]
            return Response(MeetingSerializer(rows, many=True, context=context).data)
        self._meetings_manager_only(request, project)
        serializer = MeetingInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        attendees = self._attendee_members(project, data.pop("attendees"))
        meeting = services.create_meeting(project, actor=request.user, attendees=attendees, **data)
        meeting = self._fetch_meeting(project, meeting.pk)
        return Response(MeetingSerializer(meeting, context=context).data, status=status.HTTP_201_CREATED)

    @action(
        detail=True, methods=["patch", "delete"], url_path=r"meetings/(?P<meeting_id>\d+)",
        permission_classes=[IsAuthenticated],
    )
    def meeting(self, request, pk=None, meeting_id=None):
        project = self.get_object()
        meeting = self._fetch_meeting(project, meeting_id)
        self._meetings_manager_only(request, project)
        if request.method == "DELETE":
            services.cancel_meeting(meeting, actor=request.user)
            return Response(status=status.HTTP_204_NO_CONTENT)
        serializer = MeetingUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        changes = dict(serializer.validated_data)
        if "attendees" in changes:
            changes["attendees"] = self._attendee_members(project, changes["attendees"])
        services.update_meeting(meeting, actor=request.user, changes=changes)
        meeting = self._fetch_meeting(project, meeting.pk)
        return Response(MeetingSerializer(meeting, context=self._meeting_context(request, project)).data)

    @action(
        detail=True, methods=["post"], url_path=r"meetings/(?P<meeting_id>\d+)/acknowledge",
        permission_classes=[IsAuthenticated],
    )
    def acknowledge_meeting(self, request, pk=None, meeting_id=None):
        """«مشاهده شد» — invited attendees only; idempotent (the first time is kept)."""
        project = self.get_object()
        meeting = self._fetch_meeting(project, meeting_id)
        services.acknowledge_meeting(meeting, user=request.user)
        meeting = self._fetch_meeting(project, meeting.pk)
        return Response(MeetingSerializer(meeting, context=self._meeting_context(request, project)).data)
