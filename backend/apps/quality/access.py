"""Who may do what in the quality module (Phase 18) — the one place the rule lives.

  Report            any signed-in person except the developer account
  Read              the reporter; a مسئول of the record's node or of any node above it; anyone currently
                    assigned one of its actions; a `manage_quality` holder (ستادی, کارفرمایی, so the مدیر عامل)
  Manage            `manage_quality`, **or** lead of the record's node or any node above it — the same
                    two-axis rule as documents and projects, read through `OrgAccess`, so a temporary
                    delegate (Phase 16) counts as a lead with nothing else to change

Reading is decided by **queryset scoping** (`visible_nonconformances`), as for projects: a record you may
not read is a 404 and no list route can forget the rule. `can_manage` is for writes on a record that is
already visible, so the 403 can say why.
"""
from django.db.models import Exists, OuterRef, Q
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import Capability
from apps.organization.access import OrgAccess, access_for

from .models import CorrectiveAction, NonConformance

NOT_A_MANAGER = "شما مسئول گره این مورد (یا گره‌های بالادست آن) یا مسئول کیفیت نیستید."


def can_manage(org: OrgAccess, node) -> bool:
    """`manage_quality`, or leading `node` or an ancestor. `org` is a request's `access_for` (built once)."""
    return org.holds(Capability.MANAGE_QUALITY) or org.leads(node)


def require_manager(user, node) -> None:
    if not can_manage(OrgAccess(user), node):
        raise PermissionDenied(NOT_A_MANAGER)


def can_report(user) -> bool:
    return bool(getattr(user, "is_authenticated", False)) and user.is_active and not user.is_developer


def visible_nonconformances(request):
    """The records this person may read, with the related rows a list needs."""
    queryset = NonConformance.objects.select_related("owner_node", "reported_by", "related_document")
    org = access_for(request)
    if org.holds(Capability.MANAGE_QUALITY):
        return queryset
    # An Exists, not a join through the actions: a join would repeat a record once per action.
    assigned = Exists(CorrectiveAction.objects.filter(nc=OuterRef("pk"), assignee=request.user))
    return queryset.filter(Q(reported_by=request.user) | org.led_subtree_q("owner_node__path") | Q(assigned))
