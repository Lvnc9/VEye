from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .setup_views import SetupBootstrapView, SetupCompleteView, SetupStatusView
from .views import CompanyLogoView, CompanyView, MembershipViewSet, OrgNodeViewSet, OrgTreeView, PeopleView

# SimpleRouter, not DefaultRouter: the other apps' routers already own the API root view.
router = SimpleRouter()
router.register(r"org/nodes", OrgNodeViewSet, basename="org-node")
router.register(r"org/memberships", MembershipViewSet, basename="org-membership")

urlpatterns = [
    path("setup/status/", SetupStatusView.as_view(), name="setup-status"),
    path("setup/bootstrap/", SetupBootstrapView.as_view(), name="setup-bootstrap"),
    path("setup/complete/", SetupCompleteView.as_view(), name="setup-complete"),
    path("org/tree/", OrgTreeView.as_view(), name="org-tree"),
    path("org/company/", CompanyView.as_view(), name="org-company"),
    path("org/company/logo/", CompanyLogoView.as_view(), name="org-company-logo"),
    path("org/people/", PeopleView.as_view(), name="org-people"),
    path("", include(router.urls)),
]
