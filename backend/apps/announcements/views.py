from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.pagination import DefaultPagination

from . import services
from .access import visible_announcements
from .serializers import AnnouncementCreateSerializer, AnnouncementSerializer, AnnouncementUpdateSerializer


class AnnouncementViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet
):
    """`/announcements/` — the company's notices. `get_queryset()` decides visibility
    (`visible_announcements`; anything else is a 404). The list shows the current ones — not withdrawn, not
    past their end date — pinned first, newest first; `?archive=1` shows the rest the viewer may see.
    No delete: `withdraw/`."""

    serializer_class = AnnouncementSerializer
    pagination_class = DefaultPagination
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = visible_announcements(self.request)
        if self.action != "list":
            return queryset
        current = Q(withdrawn_at__isnull=True) & (Q(expires_on__isnull=True) | Q(expires_on__gte=timezone.localdate()))
        if self.request.query_params.get("archive") in ("1", "true"):
            return queryset.exclude(current).order_by("-created_at", "-id")
        return queryset.filter(current).order_by("-pinned", "-created_at", "-id")

    def _one(self, announcement):
        return AnnouncementSerializer(visible_announcements(self.request).get(pk=announcement.pk), context=self.get_serializer_context()).data

    def create(self, request, *args, **kwargs):
        serializer = AnnouncementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(self._one(services.publish(actor=request.user, **serializer.validated_data)), status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        announcement = self.get_object()
        serializer = AnnouncementUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(self._one(services.edit(announcement, actor=request.user, changes=dict(serializer.validated_data))))

    @action(detail=True, methods=["post"])
    def withdraw(self, request, pk=None):
        return Response(self._one(services.withdraw(self.get_object(), actor=request.user)))
