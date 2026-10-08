from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import LeaveRequestViewSet

# SimpleRouter: the other apps' routers already own the API root view.
router = SimpleRouter()
router.register(r"leave/requests", LeaveRequestViewSet, basename="leave")

urlpatterns = [path("", include(router.urls))]
