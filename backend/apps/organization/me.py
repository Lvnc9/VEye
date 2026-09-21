"""What `GET /auth/me/` adds about the organisation: the company (for the sidebar's label and
logo) and the caller's own memberships.

Lives here, not in accounts, so accounts imports nothing from the org app — MeView imports this
lazily. Additive: the existing keys are unchanged, so nothing that reads /auth/me/ breaks.
"""
from .models import Company, Membership
from .serializers import company_payload


def org_context(user, request) -> dict:
    company = Company.objects.select_related("root").first()
    memberships = (
        Membership.objects.filter(user=user, node__is_active=True)
        .select_related("node")
        .order_by("-is_primary", "node__path")
    )
    return {
        "company": (
            {
                "id": company.pk,
                "name": company.root.name,
                "logo_url": company_payload(company, request)["logo_url"],
                "setup_complete": company.setup_completed_at is not None,
            }
            if company
            else None
        ),
        "memberships": [
            {
                "id": m.pk,
                "node": m.node_id,
                "node_name": m.node.name,
                "node_kind": m.node.kind,
                "is_lead": m.is_lead,
                "is_primary": m.is_primary,
            }
            for m in memberships
        ],
    }
