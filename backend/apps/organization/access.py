"""Who may do what on the organisation surfaces — the one place the rule lives.

The rule is **capability OR lead-of-an-ancestor**, and it is the composition of two
independent axes (docs/11-phase-7-9-plan.md §5.2):

  * roll × level  -> `User.capabilities` (`manage_organization`, `manage_membership`): the
    coarse "may I use this surface at all", held through the person's سمت;
  * org position  -> `Membership.is_lead` over a subtree: *which* nodes, decided by whoever
    the مدیر عامل marked as مسئول of that part of the chart.

The second axis may only **widen** access to the org surfaces (and, in later slices, projects
and chat). It never grants, withholds or changes a document capability — `workflow.py` asks
only `user.has_capability(...)`, which never reads a membership, and a test walks every
(roll, level) × lead combination to keep it that way.

Both the DRF permission classes and the serializers' "what can I do here" flags call the
functions below, so a button can never disagree with the server: they are the same code
(the pattern `workflow.next_step_for` set for the register).

Cost: `OrgAccess` is built once per request (`access_for`) and issues **one query**, the
user's lead memberships (typically 1–3 rows). Everything after is string arithmetic on
`OrgNode.path` — "is X an ancestor of N?" is `N.path.startswith(X.path)`, zero queries — and
a capability holder never even triggers that query.

Only memberships on *active* nodes confer authority: an archived node is retired, and so is
whatever its lead could do there.
"""
from django.db.models import Q
from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.accounts.models import Capability

from .models import Membership, OrgNode, OrgNodeKind


class OrgAccess:
    def __init__(self, user):
        self.user = user
        self._lead_paths: tuple[str, ...] | None = None

    # -- the two axes ---------------------------------------------------------

    def holds(self, capability: str) -> bool:
        return self.user.has_capability(capability)

    @property
    def lead_paths(self) -> tuple[str, ...]:
        """`path` of every active node this person leads. The one query."""
        if self._lead_paths is None:
            self._lead_paths = tuple(
                Membership.objects.filter(user=self.user, is_lead=True, node__is_active=True)
                .order_by("id")
                .values_list("node__path", flat=True)
            )
        return self._lead_paths

    def leads(self, node: OrgNode) -> bool:
        """Do they lead this node or any ancestor of it? (A node's own path is a prefix of
        every path beneath it, and of nothing else.)"""
        return any(node.path.startswith(path) for path in self.lead_paths)

    def led_subtree_q(self, path_field: str = "path") -> Q:
        """A filter for "rows whose node lies inside a subtree they lead" — one LIKE per lead
        membership, whatever model carries the path (`Q` over `section__path` for a project).
        Matches nothing for someone who leads nothing."""
        conditions = [Q(**{f"{path_field}__startswith": path}) for path in self.lead_paths]
        if not conditions:
            return Q(pk__in=[])
        query = conditions[0]
        for condition in conditions[1:]:
            query |= condition
        return query

    # -- the questions the org surfaces ask -----------------------------------

    def can_manage_node(self, node: OrgNode) -> bool:
        """Add things under this node, or change it: `manage_organization`, or lead of the node
        or an ancestor. The lead of a واحد can add a بخش under it without touching another واحد."""
        return self.holds(Capability.MANAGE_ORGANIZATION) or self.leads(node)

    def can_add_child(self, parent: OrgNode) -> bool:
        return self.can_manage_node(parent)

    def can_edit_node(self, node: OrgNode) -> bool:
        """Rename, move, archive, delete. The company node's name is the company profile, which
        stays with `manage_organization` alone (the root cannot move, archive or be deleted)."""
        if node.kind == OrgNodeKind.COMPANY:
            return self.holds(Capability.MANAGE_ORGANIZATION)
        return self.can_manage_node(node)

    def can_manage_members(self, node: OrgNode) -> bool:
        """Add, edit or remove the people directly in this node: `manage_membership`, or lead of
        the node or an ancestor."""
        return self.holds(Capability.MANAGE_MEMBERSHIP) or self.leads(node)


def access_for(request) -> OrgAccess:
    """The request's OrgAccess, built once (so a list of 200 nodes costs one query, not 200)."""
    access = getattr(request, "_org_access", None)
    if access is None or access.user is not request.user:
        access = request._org_access = OrgAccess(request.user)
    return access


class CanEditNode(BasePermission):
    """Writes on an existing node (PATCH, DELETE, archive, unarchive). Reads are open, and are
    scoped by nothing: any signed-in user may see the chart. Only for objects already fetched
    through the view, so the 403 can say why instead of being a bare 404."""

    message = "شما مسئول این گره یا گره‌های بالادستی آن نیستید."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return request.method in SAFE_METHODS or access_for(request).can_edit_node(obj)


class CanManageMembership(BasePermission):
    """Writes on an existing membership: allowed if the person may manage members of its node."""

    message = "شما مسئول گرهٔ این عضویت یا گره‌های بالادستی آن نیستید."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return request.method in SAFE_METHODS or access_for(request).can_manage_members(obj.node)
