"""Who may do what with leave (Phase 19) — the one place the rule lives.

  Ask        any active person except the developer account
  Decide     someone who leads the request's node or a node above it (a temporary cover counts, through
             `OrgAccess`), or the مدیر عامل — **never the requester themself**, so a مسئول's own request
             goes up the chart
  Cancel     the requester: a pending request any time, an approved one only before it starts
  Read       the requester; anyone who could decide it; `manage_personnel` (HR) and the مدیر عامل read all

Reading is queryset scoping (`visible_leave`): a request you may not read is a 404.
"""
from django.db.models import Q

from apps.accounts.models import FULL_ACCESS_POSITIONS, Capability
from apps.organization.access import OrgAccess, access_for, users_leading_at_or_above

from .models import LeaveRequest

NOT_A_DECIDER = "شما مسئول این شخص (یا گره‌های بالادست او) نیستید و نمی‌توانید دربارهٔ این مرخصی تصمیم بگیرید."


def is_top(user) -> bool:
    """The مدیر عامل (or a superuser): may decide any request."""
    return bool(user.is_superuser) or (user.access_roll, user.access_level) in FULL_ACCESS_POSITIONS


def can_decide(org: OrgAccess, leave: LeaveRequest) -> bool:
    user = org.user
    if user.pk == leave.requester_id:
        return False
    return is_top(user) or (leave.node is not None and org.leads(leave.node))


def deciders(leave: LeaveRequest):
    """Whom to tell that a request is waiting: the leads of its node and above (not the requester); with
    nobody there, the مدیر عامل. Delegates are reached through the people they cover for."""
    from apps.documents.authority import approve_eligible_users

    people = list(users_leading_at_or_above(leave.node)) if leave.node is not None else []
    people = [person for person in people if person.pk != leave.requester_id]
    if not people:
        people = [person for person in approve_eligible_users() if person.pk != leave.requester_id]
    return people


def visible_leave(request):
    queryset = LeaveRequest.objects.select_related("requester", "node", "decided_by")
    user = request.user
    org = access_for(request)
    if is_top(user) or org.holds(Capability.MANAGE_PERSONNEL):
        return queryset
    return queryset.filter(Q(requester=user) | org.led_subtree_q("node__path"))
