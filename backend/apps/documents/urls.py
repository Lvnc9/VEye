from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .history import ActivityFeedView, RevisionHistoryView
from .verify import VerifyView
from .views import DocumentViewSet

router = DefaultRouter()
router.register(r"documents", DocumentViewSet, basename="document")

urlpatterns = [
    path("verify/<str:code>/", VerifyView.as_view(), name="verify"),
    path("history/revisions/", RevisionHistoryView.as_view(), name="history-revisions"),
    path("history/activity/", ActivityFeedView.as_view(), name="history-activity"),
    path("", include(router.urls)),
]
