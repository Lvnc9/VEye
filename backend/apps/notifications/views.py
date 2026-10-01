from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.pagination import DefaultPagination

from . import services
from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """GET /notifications/ (the «اعلان‌ها» tab) and two write actions, both scoped to the
    signed-in user: nobody acts on someone else's notifications, so there is no per-object
    permission check to write — the queryset itself is the only row anyone can ever reach.
    """

    serializer_class = NotificationSerializer
    pagination_class = DefaultPagination

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = self.get_object()
        services.mark_read(notification)
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        updated = services.mark_all_read(request.user)
        return Response({"updated": updated})
