from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import serializers

from .models import Company, Membership, OrgNode, OrgNodeKind

User = get_user_model()


class OrgNodeSerializer(serializers.ModelSerializer):
    """A node as the chart needs it. `path` stays internal, and nothing here identifies a
    person — the chart is readable by anyone signed in."""

    kind_label = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = OrgNode
        fields = ["id", "parent", "kind", "kind_label", "name", "depth", "is_active"]
        read_only_fields = fields


class OrgNodeCreateSerializer(serializers.Serializer):
    #: The company root is made once, by bootstrap — never through this endpoint.
    kind = serializers.ChoiceField(choices=[c for c in OrgNodeKind.choices if c[0] != OrgNodeKind.COMPANY])
    name = serializers.CharField(max_length=255)
    parent = serializers.PrimaryKeyRelatedField(queryset=OrgNode.objects.all())


class OrgNodeUpdateSerializer(serializers.Serializer):
    """A rename and/or a move. `kind` is accepted only to say "unchanged": it is what makes
    the parent-kind constraint sound, so turning a بخش into a واحد means delete + recreate."""

    name = serializers.CharField(max_length=255, required=False)
    parent = serializers.PrimaryKeyRelatedField(queryset=OrgNode.objects.all(), required=False)
    kind = serializers.ChoiceField(choices=OrgNodeKind.choices, required=False)

    def validate_kind(self, value):
        if value != self.instance.kind:
            raise serializers.ValidationError("نوع گره پس از ساخت قابل تغییر نیست.")
        return value


class CompanyUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    legal_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    national_id = serializers.CharField(max_length=32, required=False, allow_blank=True)


def company_payload(company: Company, request) -> dict:
    logo_url = None
    if company.logo:
        # The stored name is unique per upload, so it doubles as a cache-buster.
        version = company.logo.name.rsplit("/", 1)[-1]
        logo_url = request.build_absolute_uri(reverse("org-company-logo")) + f"?v={version}"
    return {
        "id": company.pk,
        "root": company.root_id,
        "name": company.root.name,
        "legal_name": company.legal_name,
        "national_id": company.national_id,
        "logo_url": logo_url,
        "setup_step": company.setup_step,
        "setup_step_label": company.get_setup_step_display(),
        "setup_completed_at": company.setup_completed_at,
    }


class MembershipSerializer(serializers.ModelSerializer):
    """A membership as the chart needs it: who, where, and in what capacity. Never a national
    code or a phone number — the chart is readable by anyone signed in. Use with
    `select_related("user", "node")`."""

    user_name = serializers.CharField(source="user.full_name", read_only=True)
    user_title = serializers.CharField(source="user.title", read_only=True)
    user_is_active = serializers.BooleanField(source="user.is_active", read_only=True)
    node_name = serializers.CharField(source="node.name", read_only=True)
    node_kind = serializers.CharField(source="node.kind", read_only=True)

    class Meta:
        model = Membership
        fields = [
            "id",
            "user",
            "user_name",
            "user_title",
            "user_is_active",
            "node",
            "node_name",
            "node_kind",
            "is_primary",
            "is_lead",
            "position_label",
        ]
        read_only_fields = fields


class MembershipCreateSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    node = serializers.PrimaryKeyRelatedField(queryset=OrgNode.objects.all())
    is_lead = serializers.BooleanField(required=False, default=False)
    #: Omitted = "not specified": a person's first membership is primary regardless.
    is_primary = serializers.BooleanField(required=False, default=None, allow_null=True)
    position_label = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class MembershipUpdateSerializer(serializers.Serializer):
    """`user` and `node` are accepted only to say "unchanged" — to move someone, remove the
    membership and add a new one."""

    is_lead = serializers.BooleanField(required=False)
    is_primary = serializers.BooleanField(required=False)
    position_label = serializers.CharField(max_length=255, required=False, allow_blank=True)
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False)
    node = serializers.PrimaryKeyRelatedField(queryset=OrgNode.objects.all(), required=False)

    def validate(self, attrs):
        for field, current in (("user", self.instance.user_id), ("node", self.instance.node_id)):
            if field in attrs and attrs[field].pk != current:
                raise serializers.ValidationError(
                    {field: ["برای جابه‌جایی، این عضویت را حذف و عضویت تازه‌ای ایجاد کنید."]}
                )
        return attrs


class PersonMembershipSerializer(serializers.ModelSerializer):
    node_name = serializers.CharField(source="node.name", read_only=True)
    node_kind = serializers.CharField(source="node.kind", read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "node", "node_name", "node_kind", "is_primary", "is_lead", "position_label"]
        read_only_fields = fields


class PersonSerializer(serializers.ModelSerializer):
    """A person for the chart and the member picker: name, سمت and where they sit — deliberately
    *not* the national code or phone number that `/personnel/` exposes. Use with
    `prefetch_related` of memberships (`people_queryset` in views.py)."""

    title = serializers.ReadOnlyField()
    memberships = PersonMembershipSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ["id", "full_name", "title", "is_active", "memberships"]
        read_only_fields = fields
