"""Who may do what with announcements (Phase 19) — the one place the rule lives.

  Publish to the company     `manage_personnel` (HR) — the مدیر عامل holds every capability; never the
                             developer account (which holds `manage_personnel` only to register people)
  Publish to a node          HR, or a مسئول of that node or of a node above it (a temporary cover counts)
  Edit, pin, withdraw        whoever may publish to its audience (normally its author)
  Read                       a company-wide one: everyone; a node's: the people placed in that node or
                             beneath it, the مسئولان above it, HR, and its author. A withdrawn one only by
                             those who manage it.
"""
from django.db.models import Q

from apps.accounts.models import Capability
from apps.organization.access import OrgAccess, access_for, ancestor_paths

from .models import Announcement


def can_publish_to(org: OrgAccess, node) -> bool:
    """`node` None is the whole company. Never the developer account: it holds `manage_personnel` to register
    people during setup, but it speaks for nobody."""
    if org.user.is_developer:
        return False
    if org.holds(Capability.MANAGE_PERSONNEL):
        return True
    return node is not None and org.leads(node)


def can_manage(org: OrgAccess, announcement: Announcement) -> bool:
    return can_publish_to(org, announcement.audience_node)


def _manage_q(org: OrgAccess) -> Q:
    """The rows this person manages, as a filter (for showing withdrawn ones)."""
    if org.holds(Capability.MANAGE_PERSONNEL):
        return Q()
    return Q(audience_node__isnull=False) & org.led_subtree_q("audience_node__path")


def visible_announcements(request):
    queryset = Announcement.objects.select_related("author", "audience_node")
    user = request.user
    org = access_for(request)
    if org.holds(Capability.MANAGE_PERSONNEL):
        return queryset
    # Placed in a node or beneath the audience node <=> the audience node's path is an ancestor-or-self of
    # one of the person's own node paths.
    own_paths = user.memberships.values_list("node__path", flat=True)
    reachable = {path for own in own_paths for path in ancestor_paths(own)}
    readable = (
        Q(audience_node__isnull=True)
        | Q(author=user)
        | Q(audience_node__path__in=reachable)
        | org.led_subtree_q("audience_node__path")
    )
    return queryset.filter(readable).filter(Q(withdrawn_at__isnull=True) | Q(author=user) | _manage_q(org))


def audience_users(announcement: Announcement):
    """Who is told when it is published: every active person for a company-wide one; for a node, the people
    placed in it or beneath it and the مسئولان above it. Never the developer account."""
    from apps.accounts.models import User
    from apps.organization.access import users_leading_at_or_above
    from apps.organization.models import Membership

    people = User.objects.filter(is_active=True, is_developer=False)
    node = announcement.audience_node
    if node is None:
        return list(people)
    placed = Membership.objects.filter(node__path__startswith=node.path).values("user_id")
    above = users_leading_at_or_above(node).values("pk")
    return list(people.filter(Q(pk__in=placed) | Q(pk__in=above)))
