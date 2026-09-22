from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .history import AllProjectsActivityView, ProjectActivityView
from .views import ProjectViewSet

# SimpleRouter: the other apps' routers already own the API root view.
router = SimpleRouter()
router.register(r"projects", ProjectViewSet, basename="project")

urlpatterns = [
    # projects/activity/ must be registered before the router: DRF's default detail pattern is
    # projects/<pk>/ with an unrestricted lookup regex ([^/.]+), so "activity" would otherwise be
    # swallowed as a pk value (the exact pitfall documents/urls.py already avoids for bulk-print,
    # config/urls.py:9). projects/<int:pk>/activity/ has no such collision — Django's own <int:pk>
    # converter and the router's $ -anchored pattern can never match the same path — but it is kept
    # here too, beside its sibling route, rather than split across the file.
    path("projects/activity/", AllProjectsActivityView.as_view(), name="projects-activity"),
    path("projects/<int:pk>/activity/", ProjectActivityView.as_view(), name="project-activity"),
    path("", include(router.urls)),
]
