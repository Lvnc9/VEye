from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from apps.documents.models import Document
from apps.organization.models import OrgNode

from .access import can_manage_project
from .models import (
    CLOSED_OBJECTIVE_STATUSES,
    Objective,
    ObjectiveStatus,
    Project,
    ProjectComment,
    ProjectDocumentLink,
    ProjectMember,
    ProjectRole,
    ProjectStatus,
)
from .queries import progress_percent

User = get_user_model()

#: How many member avatars a list row carries.
MEMBER_PREVIEW = 5


class ProjectMemberSerializer(serializers.ModelSerializer):
    """Name, سمت and role only — never a national code or phone number."""

    user_name = serializers.CharField(source="user.full_name", read_only=True)
    user_title = serializers.CharField(source="user.title", read_only=True)
    role_label = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = ProjectMember
        fields = ["id", "user", "user_name", "user_title", "role", "role_label", "is_guest"]
        read_only_fields = fields


class ProjectSerializer(serializers.ModelSerializer):
    """A project as a list row. Needs `visible_projects()` (for `my_role`, `section`) and members
    prefetched with their users; the context must carry the request."""

    section_name = serializers.CharField(source="section.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    is_archived = serializers.BooleanField(read_only=True)
    my_role = serializers.CharField(read_only=True)
    can_edit = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    members_preview = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()
    # Annotations from queries.with_progress(), not model fields — ModelSerializer cannot infer
    # their type on its own, so they need an explicit declaration like any other computed value.
    weight_done = serializers.IntegerField(read_only=True)
    weight_total = serializers.IntegerField(read_only=True)
    objective_count = serializers.IntegerField(read_only=True)
    overdue_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Project
        fields = [
            "id", "name", "goal", "section", "section_name", "status", "status_label",
            "starts_on", "due_on", "is_archived", "archived_at", "created_at",
            "my_role", "can_edit", "member_count", "members_preview",
            "progress", "weight_done", "weight_total", "objective_count", "overdue_count",
        ]
        read_only_fields = fields

    def get_progress(self, project) -> int | None:
        """Weighted, 0–100, or null while there is nothing live to measure (queries.py)."""
        return progress_percent(project.weight_done, project.weight_total)

    def get_can_edit(self, project) -> bool:
        return can_manage_project(self.context["request"], project)

    def get_member_count(self, project) -> int:
        return len(project.members.all())

    def get_members_preview(self, project) -> list[dict]:
        return [
            {"user": m.user_id, "name": m.user.full_name, "role": m.role, "is_guest": m.is_guest}
            for m in list(project.members.all())[:MEMBER_PREVIEW]
        ]


class ProjectDetailSerializer(ProjectSerializer):
    members = ProjectMemberSerializer(many=True, read_only=True)

    class Meta(ProjectSerializer.Meta):
        fields = [*ProjectSerializer.Meta.fields, "members"]
        read_only_fields = fields


class MemberInputSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    role = serializers.ChoiceField(choices=ProjectRole.choices, required=False, default=ProjectRole.MEMBER)


class ObjectiveSerializer(serializers.ModelSerializer):
    """`assignee` is the person's *user id* (the ProjectMember behind it is an internal detail).
    `can_change_status` / `can_edit` are the viewer's rights, from the very functions the endpoints
    enforce; pass `manage` (bool) in the serializer context."""

    assignee = serializers.IntegerField(source="assignee.user_id", read_only=True)
    assignee_name = serializers.CharField(source="assignee.user.full_name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    is_overdue = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_change_status = serializers.SerializerMethodField()

    class Meta:
        model = Objective
        fields = [
            "id", "position", "title", "description", "assignee", "assignee_name", "due_on",
            "status", "status_label", "weight", "completed_at", "is_overdue", "can_edit", "can_change_status",
        ]
        read_only_fields = fields

    def get_is_overdue(self, objective) -> bool:
        return objective.due_on < timezone.localdate() and objective.status not in CLOSED_OBJECTIVE_STATUSES

    def get_can_edit(self, objective) -> bool:
        return bool(self.context.get("manage"))

    def get_can_change_status(self, objective) -> bool:
        return bool(self.context.get("manage")) or objective.assignee.user_id == self.context["request"].user.pk


class ObjectiveInputSerializer(serializers.Serializer):
    """One objective to create. Assignee and deadline are both required: no unassigned backlog."""

    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    assignee = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    due_on = serializers.DateField()
    weight = serializers.IntegerField(min_value=1, max_value=100, required=False, default=1)


class ObjectiveUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    assignee = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False)
    due_on = serializers.DateField(required=False)
    status = serializers.ChoiceField(choices=ObjectiveStatus.choices, required=False)
    weight = serializers.IntegerField(min_value=1, max_value=100, required=False)


class ReorderSerializer(serializers.Serializer):
    order = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)


class ProjectCreateSerializer(serializers.Serializer):
    section = serializers.PrimaryKeyRelatedField(queryset=OrgNode.objects.all())
    name = serializers.CharField(max_length=255)
    goal = serializers.CharField(required=False, allow_blank=True, default="")
    starts_on = serializers.DateField(required=False, allow_null=True, default=None)
    due_on = serializers.DateField(required=False, allow_null=True, default=None)
    members = MemberInputSerializer(many=True, required=False, default=list)
    objectives = ObjectiveInputSerializer(many=True, required=False, default=list)


class ProjectUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    goal = serializers.CharField(required=False, allow_blank=True)
    starts_on = serializers.DateField(required=False, allow_null=True)
    due_on = serializers.DateField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=ProjectStatus.choices, required=False)


class MemberCreateSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    role = serializers.ChoiceField(choices=ProjectRole.choices, required=False, default=ProjectRole.MEMBER)


class MemberUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=ProjectRole.choices)


class ProjectCommentSerializer(serializers.ModelSerializer):
    """A human note on a project or on one of its objectives. `author` is the person's user id (or
    null once they are deactivated and the FK has gone through `SET_NULL`); `author_name`/
    `author_title` are the durable, always-present snapshot. `can_delete` mirrors the one rule the
    view enforces: **the author only, no exception** — not the project's manager, not مدیر عامل."""

    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = ProjectComment
        fields = ["id", "objective", "author", "author_name", "author_title", "body", "created_at", "can_delete"]
        read_only_fields = fields

    def get_can_delete(self, comment) -> bool:
        return comment.author_id == self.context["request"].user.pk


class CommentCreateSerializer(serializers.Serializer):
    body = serializers.CharField()
    #: A comment on the project as a whole when omitted; the service checks it belongs to this project.
    objective = serializers.PrimaryKeyRelatedField(
        queryset=Objective.objects.all(), required=False, allow_null=True, default=None
    )


class ProjectDocumentLinkSerializer(serializers.ModelSerializer):
    """`document` is exposed by id only — the register itself already carries the rest (title,
    full_code, status); duplicating that here would be a second place for it to go stale."""

    document_full_code = serializers.CharField(source="document.full_code", read_only=True)
    document_title = serializers.CharField(source="document.title", read_only=True)
    linked_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ProjectDocumentLink
        fields = [
            "id", "document", "document_full_code", "document_title", "caption", "linked_by_name", "created_at",
        ]
        read_only_fields = fields

    def get_linked_by_name(self, link) -> str:
        return link.linked_by.full_name if link.linked_by_id else ""


class DocumentLinkCreateSerializer(serializers.Serializer):
    document = serializers.PrimaryKeyRelatedField(queryset=Document.objects.all())
    caption = serializers.CharField(required=False, allow_blank=True, default="")
