from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .history import AllQualityActivityView, AuditActivityView, NonConformanceActivityView
from .views import AuditViewSet, NonConformanceViewSet

# SimpleRouter: the other apps' routers already own the API root view.
router = SimpleRouter()
router.register(r"quality/nonconformances", NonConformanceViewSet, basename="nonconformance")
router.register(r"quality/audits", AuditViewSet, basename="audit")

urlpatterns = [
    # quality/activity/ and the per-record feed sit beside the router; neither collides with
    # nonconformances/<pk>/ (different prefix / extra segment).
    path("quality/activity/", AllQualityActivityView.as_view(), name="quality-activity"),
    path("quality/nonconformances/<int:pk>/activity/", NonConformanceActivityView.as_view(), name="nonconformance-activity"),
    path("quality/audits/<int:pk>/activity/", AuditActivityView.as_view(), name="audit-activity"),
    path("", include(router.urls)),
]
