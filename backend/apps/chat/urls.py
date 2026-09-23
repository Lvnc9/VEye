from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import ConversationViewSet

# SimpleRouter: the other apps' routers already own the API root view.
router = SimpleRouter()
router.register(r"chat/conversations", ConversationViewSet, basename="conversation")

urlpatterns = [path("", include(router.urls))]
