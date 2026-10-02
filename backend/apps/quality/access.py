"""Who may do what in the quality module (Phase 18) — the one place the rule lives.

  Report            any signed-in person except the developer account
  Read              the reporter; a مسئول of the record's node or of any node above it; anyone currently
                    assigned one of its actions; a `manage_quality` holder (ستادی, کارفرمایی, so the مدیر عامل)
  Manage            `manage_quality`, **or** lead of the record's node or any node above it — the same
                    two-axis rule as documents and projects, read through `OrgAccess`, so a temporary
                    delegate (Phase 16) counts as a lead with nothing else to change

  Plan / cancel an audit      `manage_quality` alone — an independent function: the lead of a unit does not
                              schedule, or call off, the audit of their own unit
  Run an audit                its lead auditor, or `manage_quality`: start, complete, raise findings
  Read an audit               `manage_quality`; its lead auditor; a مسئول of its scope node or of any node above
  Read a finding              as any non-conformance, **plus** the lead auditor of the audit that raised it (so
                              the auditor keeps sight of what a quality manager raised on their behalf)

Reading is decided by **queryset scoping** (`visible_nonconformances`, `visible_audits`), as for projects: a
record you may not read is a 404 and no list route can forget the rule. `can_manage` is for writes on a record
that is already visible, so the 403 can say why.
"""
from django.db.models import Exists, OuterRef, Q
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import Capability
from apps.organization.access import OrgAccess, access_for

from .models import CorrectiveAction, InternalAudit, NonConformance

NOT_A_MANAGER = "شما مسئول گره این مورد (یا گره‌های بالادست آن) یا مسئول کیفیت نیستید."
NOT_A_QUALITY_MANAGER = "فقط مسئول کیفیت می‌تواند ممیزی را برنامه‌ریزی، ویرایش یا لغو کند."
NOT_THE_AUDITOR = "فقط ممیز اصلی این ممیزی یا مسئول کیفیت می‌تواند این کار را انجام دهد."


def can_manage(org: OrgAccess, node) -> bool:
    """`manage_quality`, or leading `node` or an ancestor. `org` is a request's `access_for` (built once)."""
    return org.holds(Capability.MANAGE_QUALITY) or org.leads(node)


def require_manager(user, node) -> None:
    if not can_manage(OrgAccess(user), node):
        raise PermissionDenied(NOT_A_MANAGER)


def can_plan_audits(org: OrgAccess) -> bool:
    """Planning, editing and cancelling an audit: `manage_quality`, and nothing from the chart."""
    return org.holds(Capability.MANAGE_QUALITY)


def require_audit_planner(user) -> None:
    if not can_plan_audits(OrgAccess(user)):
        raise PermissionDenied(NOT_A_QUALITY_MANAGER)


def can_run_audit(org: OrgAccess, audit: InternalAudit) -> bool:
    """Start, complete and raise findings: the lead auditor, or `manage_quality`."""
    return audit.lead_auditor_id == org.user.pk or can_plan_audits(org)


def require_audit_runner(user, audit: InternalAudit) -> None:
    if not can_run_audit(OrgAccess(user), audit):
        raise PermissionDenied(NOT_THE_AUDITOR)


def can_report(user) -> bool:
    return bool(getattr(user, "is_authenticated", False)) and user.is_active and not user.is_developer


def visible_nonconformances(request):
    """The records this person may read, with the related rows a list needs."""
    queryset = NonConformance.objects.select_related(
        "owner_node", "reported_by", "related_document", "audit", "audit__scope_node"
    )
    org = access_for(request)
    if org.holds(Capability.MANAGE_QUALITY):
        return queryset
    # An Exists, not a join through the actions: a join would repeat a record once per action.
    assigned = Exists(CorrectiveAction.objects.filter(nc=OuterRef("pk"), assignee=request.user))
    # `audit__lead_auditor` is a forward single-valued join, so it cannot repeat a row either.
    return queryset.filter(
        Q(reported_by=request.user)
        | org.led_subtree_q("owner_node__path")
        | Q(assigned)
        | Q(audit__lead_auditor=request.user)
    )


def can_read_audit(org: OrgAccess, audit: InternalAudit) -> bool:
    """The same rule as `visible_audits`, for one audit already in hand (a finding's «از ممیزی …» link is
    shown only to someone who can open it: a مسئول of a بخش beneath the scope reads the finding but not
    the audit). `audit.scope_node` should be loaded."""
    return org.holds(Capability.MANAGE_QUALITY) or audit.lead_auditor_id == org.user.pk or org.leads(audit.scope_node)


def visible_audits(request):
    """The audits this person may read."""
    queryset = InternalAudit.objects.select_related("scope_node", "lead_auditor")
    org = access_for(request)
    if org.holds(Capability.MANAGE_QUALITY):
        return queryset
    return queryset.filter(Q(lead_auditor=request.user) | org.led_subtree_q("scope_node__path"))
