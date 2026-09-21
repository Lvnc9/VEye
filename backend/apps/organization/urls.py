from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import CompanyLogoView, CompanyView, OrgNodeViewSet, OrgTreeView

# SimpleRouter, not DefaultRouter: the other apps' routers already own the API root view.
router = SimpleRouter()
router.register(r"org/nodes", OrgNodeViewSet, basename="org-node")

urlpatterns = [
    path("org/tree/", OrgTreeView.as_view(), name="org-tree"),
    path("org/company/", CompanyView.as_view(), name="org-company"),
    path("org/company/logo/", CompanyLogoView.as_view(), name="org-company-logo"),
    path("", include(router.urls)),
]
