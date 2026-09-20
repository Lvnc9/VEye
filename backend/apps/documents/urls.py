from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .verify import VerifyView
from .views import DocumentViewSet

router = DefaultRouter()
router.register(r"documents", DocumentViewSet, basename="document")

urlpatterns = [
    path("verify/<str:code>/", VerifyView.as_view(), name="verify"),
    path("", include(router.urls)),
]
