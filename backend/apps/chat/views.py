from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import F, Prefetch
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.pagination import DefaultPagination
from apps.organization.models import OrgNode

from . import services
from .access import chat_access_for
from .models import ConversationParticipant, Message
from .queries import with_viewer_state
from .serializers import (
    ConversationSerializer,
    MarkReadSerializer,
    MessageSerializer,
    OpenDirectSerializer,
    OpenNodeSerializer,
    SendMessageSerializer,
)

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
        return (
            with_viewer_state(queryset, self.request.user)
            .prefetch_related(Prefetch("participants", queryset=ConversationParticipant.objects.select_related("user")))
            .order_by(F("last_message_at").desc(nulls_last=True), "-id")
        )

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

    # -- messages ---------------------------------------------------------------

    def _cursor(self, request, name):
        raw = request.query_params.get(name)
        if raw in (None, ""):
            return None
        try:
            value = int(raw)
        except ValueError:
            raise ValidationError({name: ["شناسهٔ پیام باید عدد باشد."]})
        if value < 0:
            raise ValidationError({name: ["شناسهٔ پیام باید عدد باشد."]})
        return value

    def _limit(self, request):
        raw = request.query_params.get("limit")
        if raw in (None, ""):
            return settings.CHAT_PAGE_SIZE
        try:
            return max(1, min(int(raw), settings.CHAT_MAX_PAGE_SIZE))
        except ValueError:
            raise ValidationError({"limit": ["تعداد باید عدد باشد."]})

    def _list_messages(self, request, conversation):
        """Cursor paging on message id — no COUNT, no offsets, stable while people keep writing.

          (none)        the newest `limit` messages
          ?before=<id>  the `limit` messages just older than <id> (scrolling up)
          ?after=<id>   messages newer than <id>, oldest first (polling — usually empty and cheap)

        Always ascending. `has_more` says whether another page exists in the direction asked."""
        before, after = self._cursor(request, "before"), self._cursor(request, "after")
        if before is not None and after is not None:
            raise ValidationError({"detail": "فقط یکی از before یا after را بفرستید."})
        limit = self._limit(request)
        messages = Message.objects.filter(conversation=conversation)
        if after is not None:
            rows = list(messages.filter(id__gt=after).order_by("id")[: limit + 1])
            has_more = len(rows) > limit
            rows = rows[:limit]
        else:
            if before is not None:
                messages = messages.filter(id__lt=before)
            rows = list(messages.order_by("-id")[: limit + 1])
            has_more = len(rows) > limit
            rows = list(reversed(rows[:limit]))
        serializer = MessageSerializer(rows, many=True, context=self.get_serializer_context())
        return Response({"results": serializer.data, "has_more": has_more})

    @method_decorator(
        ratelimit(key="user", rate=lambda group, request: settings.CHAT_SEND_RATELIMIT_RATE, method="POST", block=True)
    )
    @action(detail=True, methods=["get", "post"])
    def messages(self, request, pk=None):
        conversation = self.get_object()
        if request.method == "GET":
            return self._list_messages(request, conversation)
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = services.send_message(conversation, sender=request.user, body=serializer.validated_data["body"])
        data = MessageSerializer(message, context=self.get_serializer_context()).data
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"messages/(?P<message_id>[0-9]+)")
    def message(self, request, pk=None, message_id=None):
        conversation = self.get_object()
        message = Message.objects.filter(conversation=conversation, pk=message_id).first()
        if message is None:
            raise NotFound("پیام یافت نشد.")
        message = services.delete_message(message, actor=request.user)
        return Response(MessageSerializer(message, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        """Move my read mark forward (never back). Answers the mark now stored."""
        conversation = self.get_object()
        serializer = MarkReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mark = services.mark_read(conversation, user=request.user, up_to=serializer.validated_data["message"])
        return Response({"last_read_message_id": mark})
