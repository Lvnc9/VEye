from django.urls import reverse
from rest_framework import serializers

from .models import Company, OrgNode, OrgNodeKind


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
