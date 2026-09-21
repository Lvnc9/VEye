from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import ProjectViewSet

# SimpleRouter: the other apps' routers already own the API root view.
router = SimpleRouter()
router.register(r"projects", ProjectViewSet, basename="project")

urlpatterns = [
    path("", include(router.urls)),
]
