from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import HolidayViewSet, LeaveRequestViewSet

# SimpleRouter: the other apps' routers already own the API root view.
router = SimpleRouter()
router.register(r"leave/requests", LeaveRequestViewSet, basename="leave")
router.register(r"leave/holidays", HolidayViewSet, basename="holiday")

urlpatterns = [path("", include(router.urls))]
