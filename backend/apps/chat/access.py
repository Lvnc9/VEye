"""Who may read a conversation — the chat half of docs/11 §5.3.

  DIRECT   its two participants. **No override of any kind, ever — not even مدیر عامل.** There is
           no capability for it and there must never be one: the مدیر عامل is built from
           `Capability.values`, so a capability would silently hand that position everyone's DMs.
  NODE     a membership on that node, or a lead membership on an active ancestor (the owner's
           decision — members are told the channel is visible to leads above them).
  root     the company-wide channel: anyone with a membership anywhere (owner's decision; the
           strict rule above would admit only the people placed on the company node itself).

Reads are decided by **queryset scoping** only (`visible_conversations`), so an invisible
conversation is a 404 and no list route can forget the rule. Cost: the lead paths come from the
request's `OrgAccess` (one query), plus one query for the person's own membership node ids.
"""
from django.db.models import Exists, OuterRef, Q

from apps.organization.access import OrgAccess, access_for
from apps.organization.models import Membership, OrgNode, OrgNodeKind

from .models import Conversation, ConversationKind, ConversationParticipant


class ChatAccess:
    def __init__(self, user, org: OrgAccess | None = None):
        self.user = user
        self.org = org or OrgAccess(user)
        self._member_node_ids: frozenset[int] | None = None

    @property
    def member_node_ids(self) -> frozenset[int]:
        if self._member_node_ids is None:
            self._member_node_ids = frozenset(
                Membership.objects.filter(user=self.user).values_list("node_id", flat=True)
            )
        return self._member_node_ids

    def can_read_node(self, node: OrgNode) -> bool:
        if node.kind == OrgNodeKind.COMPANY:
            return bool(self.member_node_ids)
        return node.pk in self.member_node_ids or self.org.leads(node)

    def can_read(self, conversation: Conversation) -> bool:
        if conversation.kind == ConversationKind.DIRECT:
            return conversation.participants.filter(user=self.user).exists()
        return self.can_read_node(conversation.node)

    def _node_q(self) -> Q:
        query = Q(node_id__in=self.member_node_ids) | self.org.led_subtree_q("node__path")
        if self.member_node_ids:
            query |= Q(node__kind=OrgNodeKind.COMPANY)
        return Q(kind=ConversationKind.NODE) & query

    def _participant_exists(self):
        return Exists(ConversationParticipant.objects.filter(conversation=OuterRef("pk"), user=self.user))

    def visible_conversations(self):
        """Every conversation this person may open."""
        return (
            Conversation.objects.select_related("node")
            .annotate(is_participant=self._participant_exists())
            .filter(Q(kind=ConversationKind.DIRECT, is_participant=True) | self._node_q())
        )

    def listed_conversations(self):
        """What «گفتگوها» shows: their DMs, the channels of their own nodes, the company channel,
        and any other channel they may read *and* have opened. A lead may open every channel below
        them, but a مدیر عامل's list must not be every بخش in the company (owner's decision)."""
        own_nodes = Q(node_id__in=self.member_node_ids)
        if self.member_node_ids:
            own_nodes |= Q(node__kind=OrgNodeKind.COMPANY)
        return self.visible_conversations().filter(Q(is_participant=True) | own_nodes)


def chat_access_for(request) -> ChatAccess:
    """The request's ChatAccess, built once and sharing the request's OrgAccess."""
    access = getattr(request, "_chat_access", None)
    if access is None or access.user is not request.user:
        access = request._chat_access = ChatAccess(request.user, access_for(request))
    return access
