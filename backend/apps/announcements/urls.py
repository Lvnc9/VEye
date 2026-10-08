from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import AnnouncementViewSet

router = SimpleRouter()
router.register(r"announcements", AnnouncementViewSet, basename="announcement")

urlpatterns = [path("", include(router.urls))]
