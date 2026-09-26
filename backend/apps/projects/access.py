"""Who may do what with projects — the project half of docs/11 §5.3, composed from the org half.

  Create a project      `create_project`, or lead of the target بخش (or an ancestor)
  Read a project        a ProjectMember, or lead of its بخش (or an ancestor), or `manage_organization`
  Edit / manage         its مدیر پروژه, or lead of its بخش (or an ancestor), or any کارفرمایی account
  Meetings (write)      its مدیر پروژه, or any کارفرمایی account — not a بخش lead; never while archived

Reading is decided by **queryset scoping** (`visible_projects`), so an invisible project is a 404
and no list route can forget the rule; `can_manage` is for writes on a project that is already
visible, so the 403 can say why. The org half (leads, capabilities) comes from
`organization.access.OrgAccess` — one query per request, then prefix arithmetic on `OrgNode.path`.
"""
from django.db.models import OuterRef, Q, Subquery
from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.accounts.models import AccessRoll, Capability
from apps.organization.access import access_for

from .models import Project, ProjectMember, ProjectRole


def visible_projects(request):
    """Projects this person may read, each annotated with `my_role` (their ProjectMember role, or
    None). Members' rows are always visible to themselves; leads see their whole subtree;
    `manage_organization` sees everything."""
    user = request.user
    my_role = Subquery(ProjectMember.objects.filter(project=OuterRef("pk"), user=user).values("role")[:1])
    queryset = Project.objects.select_related("section").annotate(my_role=my_role)
    org = access_for(request)
    if org.holds(Capability.MANAGE_ORGANIZATION):
        return queryset
    return queryset.filter(Q(my_role__isnull=False) | org.led_subtree_q("section__path"))


def can_create_project(request, section) -> bool:
    org = access_for(request)
    return org.holds(Capability.CREATE_PROJECT) or org.leads(section)


def can_manage_project(request, project) -> bool:
    """`project` must come from `visible_projects` (it needs `my_role` and `section`).

    Every کارفرمایی account — the مدیر عامل and the board, all levels — may edit every project, without
    needing a lead membership (owner, 2026-09-26). Checked on the roll rather than as a new capability,
    so the per-roll capability sets stay untouched. The developer account is صفی/لول ۳ and never gets it."""
    if request.user.access_roll == AccessRoll.EMPLOYER:
        return True
    return project.my_role == ProjectRole.MANAGER or access_for(request).leads(project.section)


def can_manage_meetings(request, project) -> bool:
    """Create, edit or cancel a meeting. Narrower than `can_manage_project` on purpose: ADR-010 gave
    meetings to the project's MANAGER role only (not a بخش lead), and the owner added every
    کارفرمایی account on 2026-09-26. False while the project is archived, since the flag also drives
    whether the frontend shows the form at all. `project` must come from `visible_projects`."""
    if project.is_archived:
        return False
    return project.my_role == ProjectRole.MANAGER or request.user.access_roll == AccessRoll.EMPLOYER


class CanManageProject(BasePermission):
    message = "شما مدیر این پروژه نیستید."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return request.method in SAFE_METHODS or can_manage_project(request, obj)
