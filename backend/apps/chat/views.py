from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import F, Prefetch
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.pagination import DefaultPagination
from apps.organization.models import OrgNode

from . import services
from .access import chat_access_for
from .models import ConversationParticipant
from .serializers import ConversationSerializer, OpenDirectSerializer, OpenNodeSerializer

User = get_user_model()

NODE_CHANNEL_FORBIDDEN = "شما عضو این گره یا مسئول گره‌های بالادستی آن نیستید."


class ConversationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """`/chat/conversations/` — what «گفتگوها» lists (`listed_conversations`), and any conversation
    the caller may read (`visible_conversations`, so an invisible one is a 404 with no existence
    leak). Newest activity first; a never-used conversation sorts after every used one."""

    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = DefaultPagination

    def get_queryset(self):
        access = chat_access_for(self.request)
        queryset = access.listed_conversations() if self.action == "list" else access.visible_conversations()
        return queryset.prefetch_related(
            Prefetch("participants", queryset=ConversationParticipant.objects.select_related("user"))
        ).order_by(F("last_message_at").desc(nulls_last=True), "-id")

    def _respond(self, conversation, created: bool):
        conversation = self.get_queryset().get(pk=conversation.pk)
        data = self.get_serializer(conversation).data
        return Response(data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @method_decorator(
        ratelimit(
            key="user", rate=lambda group, request: settings.CHAT_OPEN_DIRECT_RATELIMIT_RATE, method="POST", block=True
        )
    )
    @action(detail=False, methods=["post"])
    def direct(self, request):
        """Open (or find) the DM with another person: 201 when new, 200 when it already existed."""
        serializer = OpenDirectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        other = User.objects.filter(pk=serializer.validated_data["user"]).first()
        if other is None:
            raise NotFound("شخص یافت نشد.")
        conversation, created = services.open_direct(actor=request.user, other=other)
        return self._respond(conversation, created)

    @action(detail=False, methods=["post"])
    def node(self, request):
        """Open a node's group channel. The chart is readable by everyone, so a channel the caller
        may not read is a 403 that says why, not a 404."""
        serializer = OpenNodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        node = OrgNode.objects.filter(pk=serializer.validated_data["node"]).first()
        if node is None:
            raise NotFound("گره یافت نشد.")
        if not chat_access_for(request).can_read_node(node):
            raise PermissionDenied(NODE_CHANNEL_FORBIDDEN)
        conversation = services.open_node_conversation(actor=request.user, node=node)
        return self._respond(conversation, created=False)
