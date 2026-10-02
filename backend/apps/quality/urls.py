from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .history import AllQualityActivityView, NonConformanceActivityView
from .views import NonConformanceViewSet

# SimpleRouter: the other apps' routers already own the API root view.
router = SimpleRouter()
router.register(r"quality/nonconformances", NonConformanceViewSet, basename="nonconformance")

urlpatterns = [
    # quality/activity/ and the per-record feed sit beside the router; neither collides with
    # nonconformances/<pk>/ (different prefix / extra segment).
    path("quality/activity/", AllQualityActivityView.as_view(), name="quality-activity"),
    path("quality/nonconformances/<int:pk>/activity/", NonConformanceActivityView.as_view(), name="nonconformance-activity"),
    path("", include(router.urls)),
]
