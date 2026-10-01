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

from functools import reduce
from operator import or_

from django.db.models import Q
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import FULL_ACCESS_POSITIONS, Capability, User
from apps.organization.access import OrgAccess
from apps.organization.models import OrgNode, OrgNodeKind


def is_managing_director(user) -> bool:
    """The مدیر عامل (کارفرمایی, لول ۱) — the only person who approves — and a superuser. The developer
    account is neither: it shapes the chart and never signs a document."""
    if not getattr(user, "is_authenticated", False) or not user.is_active or user.is_developer:
        return False
    return user.is_superuser or (user.access_roll, user.access_level) in FULL_ACCESS_POSITIONS


#: Who may confirm a document: the مسئول of a واحد, a حوزه or the شرکت above it — never of a بخش.
CONFIRMING_KINDS = frozenset({OrgNodeKind.UNIT, OrgNodeKind.DOMAIN, OrgNodeKind.COMPANY})

NOT_AN_AUTHOR = "شما مسئول گرهٔ این مستند (یا گره‌های بالادستی آن) نیستید و نمی‌توانید آن را ویرایش یا ارسال کنید."
NOT_A_CONFIRMER = "فقط مسئول واحد یا حوزهٔ ذی‌ربط این مستند (یا مسئولان بالاتر) می‌تواند آن را تایید کند."
NOT_THE_APPROVER = "تصویب مستندات فقط بر عهدهٔ مدیر عامل است."
LEADS_NOTHING = "شما مسئول هیچ گره‌ای در ساختار سازمانی نیستید و نمی‌توانید مستند بسازید."


class DocumentAuthority:
    """Who may do what with documents, for one person — built once per request (`for_request`), so
    the register's buttons, the dashboard and the workflow endpoints all ask the same object.

    The owner's rules (2026-09-30), applied to a document's owner node N:

      * تدوین — the مسئول of N or of any node above it (a بخش's lead writes that بخش's documents; a
        واحد's lead those of the واحد and its بخش‌ها; a حوزه's lead everything beneath it);
      * تایید — the مسئول of N or of a node above it that is a واحد, a حوزه or the شرکت (a بخش's lead
        does not confirm); the same person may write and confirm;
      * تصویب — only the مدیر عامل, whatever he wrote or confirmed himself;
      * the مدیر عامل (and a superuser) may also write and confirm anything;
      * a document with no owner node — one that predates the chart — is acted on by the مدیر عامل only;
      * a member who leads nothing, someone with no placement, and the developer account act on nothing.

    Only leads of *active* nodes count (`OrgAccess`): an archived node's lead is retired with it.
    """

    def __init__(self, user, access: OrgAccess | None = None):
        self.user = user
        self.access = access or OrgAccess(user)
        self.is_director = is_managing_director(user)
        #: The developer account, an inactive one and an anonymous visitor never act on a document.
        self.acts = bool(getattr(user, "is_authenticated", False)) and bool(user.is_active) and not user.is_developer

    # -- one document ---------------------------------------------------------

    def can_author(self, document) -> bool:
        if self.is_director:
            return True
        node = document.owner_node
        return self.acts and node is not None and self.access.leads(node)

    def can_confirm(self, document) -> bool:
        if self.is_director:
            return True
        node = document.owner_node
        return self.acts and node is not None and self.access.leads_of_kind(node, CONFIRMING_KINDS)

    def can_approve(self, document=None) -> bool:
        return self.is_director

    # -- anywhere (what /auth/me/ and the create form need) -------------------

    @property
    def can_author_anywhere(self) -> bool:
        return self.is_director or (self.acts and bool(self.access.lead_nodes))

    @property
    def can_confirm_anywhere(self) -> bool:
        return self.is_director or (
            self.acts and any(kind in CONFIRMING_KINDS for _, kind in self.access.lead_nodes)
        )

    # -- queries: the documents someone may act on ----------------------------

    def _subtree_q(self, kinds=None) -> Q:
        paths = [path for path, kind in self.access.lead_nodes if kinds is None or kind in kinds]
        if not self.acts or not paths:
            return Q(pk__in=[])
        query = Q(owner_node__path__startswith=paths[0])
        for path in paths[1:]:
            query |= Q(owner_node__path__startswith=path)
        return query

    def authoring_q(self) -> Q:
        """Documents this person may write: any (the مدیر عامل), or those whose owner node lies in a subtree they lead."""
        return Q() if self.is_director else self._subtree_q()

    def confirming_q(self) -> Q:
        """Documents this person may confirm: any (the مدیر عامل), or those under a واحد / حوزه / شرکت they lead."""
        return Q() if self.is_director else self._subtree_q(CONFIRMING_KINDS)

    # -- refusals -------------------------------------------------------------

    def require_author(self, document) -> None:
        if not self.can_author(document):
            raise PermissionDenied(NOT_AN_AUTHOR)


def for_request(request) -> DocumentAuthority:
    """The request's DocumentAuthority, built once (a register page costs one lead query, not one per row)."""
    authority = getattr(request, "_document_authority", None)
    if authority is None or authority.user is not request.user:
        authority = request._document_authority = DocumentAuthority(request.user)
    return authority


def effective_capabilities(user) -> frozenset[str]:
    """`user.capabilities` (roll-based; the مدیر عامل and a superuser hold all) plus the three document
    capabilities as the org chart grants them — for `/auth/me/`, so the UI can show or hide the create
    button and the sidebar. Whether a person may act on *this* document is `DocumentAuthority`'s answer,
    served with each register row."""
    capabilities = set(user.capabilities)
    authority = DocumentAuthority(user)
    if authority.can_author_anywhere:
        capabilities.add(Capability.CREATE_DOCUMENT)
    if authority.can_confirm_anywhere:
        capabilities.add(Capability.CONFIRM_DOCUMENT)
    if authority.can_approve():
        capabilities.add(Capability.APPROVE_DOCUMENT)
    return frozenset(capabilities)


def eligible_owner_nodes(user, access: OrgAccess | None = None):
    """The active nodes a document of `user` may belong to: everything at or below a node they lead;
    for the مدیر عامل, the whole chart. Nothing for someone who leads nothing, or the developer."""
    nodes = OrgNode.objects.filter(is_active=True)
    authority = DocumentAuthority(user, access)
    if authority.is_director:
        return nodes
    if not authority.acts:
        return nodes.none()
    return nodes.filter(authority.access.led_subtree_q())


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


# -- who to notify (Phase 15) -------------------------------------------------
#
# The functions above answer "may *this* person act?"; a reminder needs the opposite question —
# "who *are* all the people who could?" — so `workflow.py` knows who to tell. Kept here, not in
# `apps.notifications`, because it is exactly the Phase 14 rule above, read backwards; the
# structural guard in `apps/organization/tests.py` (`test_no_document_module_reads_the_org_tables`)
# still holds, since the org-side lookup itself lives in `organization.access`, not here.


def approve_eligible_users():
    """Everyone who could approve any document right now: the مدیر عامل position(s) and every
    superuser. Used to notify them when a document reaches AWAITING_APPROVAL, and as the fallback
    for a document with no owner node (nobody else can act on one anyway)."""
    position_q = reduce(or_, (Q(access_roll=roll, access_level=level) for roll, level in FULL_ACCESS_POSITIONS))
    return User.objects.filter(is_active=True, is_developer=False).filter(Q(is_superuser=True) | position_q)


def confirm_eligible_users(document):
    """Everyone who could confirm `document` right now: the مسئول of a واحد / حوزه / شرکت at or
    above its owner node, plus the مدیر عامل (who may always act). A document predating the chart
    (`owner_node` is NULL) has only the مدیر عامل to tell."""
    if document.owner_node_id is None:
        return approve_eligible_users()
    from apps.organization.access import users_leading_at_or_above

    leads = users_leading_at_or_above(document.owner_node, kinds=CONFIRMING_KINDS)
    return (leads | approve_eligible_users()).distinct()
