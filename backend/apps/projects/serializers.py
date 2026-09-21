from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.organization.models import OrgNode

from .access import can_manage_project
from .models import Project, ProjectMember, ProjectRole, ProjectStatus

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

    class Meta:
        model = Project
        fields = [
            "id", "name", "goal", "section", "section_name", "status", "status_label",
            "starts_on", "due_on", "is_archived", "archived_at", "created_at",
            "my_role", "can_edit", "member_count", "members_preview",
        ]
        read_only_fields = fields

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


class ProjectCreateSerializer(serializers.Serializer):
    section = serializers.PrimaryKeyRelatedField(queryset=OrgNode.objects.all())
    name = serializers.CharField(max_length=255)
    goal = serializers.CharField(required=False, allow_blank=True, default="")
    starts_on = serializers.DateField(required=False, allow_null=True, default=None)
    due_on = serializers.DateField(required=False, allow_null=True, default=None)
    members = MemberInputSerializer(many=True, required=False, default=list)


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
