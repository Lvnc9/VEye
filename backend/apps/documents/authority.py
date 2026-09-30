"""Who may act on a document — decided by the org chart (Phase 14, the owner's rules of 2026-09-30).

A document belongs to an **owner node** (`Document.owner_node`: a بخش, واحد, حوزه or the شرکت). Which
people may write it, confirm it or approve it follows from who *leads* that node or one above it, not
from their roll × level — see docs/09-workflow.md. This module is the single home of those rules and,
with `responsibility_nodes.py`, the only place under `apps/documents` that reads the org app.

It builds on `organization.access.OrgAccess` (one query per request for the nodes a person leads,
then path arithmetic), so the register's buttons, the dashboard and the workflow endpoints cannot
disagree: they call the same functions.
"""
from __future__ import annotations

from apps.accounts.models import FULL_ACCESS_POSITIONS
from apps.organization.access import OrgAccess
from apps.organization.models import OrgNode


def is_managing_director(user) -> bool:
    """The مدیر عامل (کارفرمایی, لول ۱) — the only person who approves — and a superuser. The developer
    account is neither: it shapes the chart and never signs a document."""
    if not getattr(user, "is_authenticated", False) or not user.is_active or user.is_developer:
        return False
    return user.is_superuser or (user.access_roll, user.access_level) in FULL_ACCESS_POSITIONS


def eligible_owner_nodes(user, access: OrgAccess | None = None):
    """The active nodes a document of `user` may belong to: everything at or below a node they lead;
    for the مدیر عامل, the whole chart. Nothing for someone who leads nothing."""
    nodes = OrgNode.objects.filter(is_active=True)
    if is_managing_director(user):
        return nodes
    if not getattr(user, "is_authenticated", False):
        return nodes.none()
    return nodes.filter((access or OrgAccess(user)).led_subtree_q())


def owner_node_choices(user) -> list[dict]:
    """`eligible_owner_nodes` as the picker lists them, in chart order: id, name, kind, depth and a
    «حوزه › واحد» label (the company's own name is left out — it is the same for everyone)."""
    names = {pk: (parent, name) for pk, parent, name in OrgNode.objects.values_list("pk", "parent_id", "name")}

    def label(pk) -> str:
        parts = []
        while pk is not None:
            parent, name = names[pk]
            if parent is not None:
                parts.append(name)
            pk = parent
        return " › ".join(reversed(parts))

    return [
        {
            "id": node.pk,
            "name": node.name,
            "kind": node.kind,
            "kind_label": node.get_kind_display(),
            "depth": node.depth,
            "label": label(node.pk) or node.name,
        }
        for node in eligible_owner_nodes(user)
    ]
