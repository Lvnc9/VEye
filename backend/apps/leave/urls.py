from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import BalancesView, BalanceView, EntitlementView, HolidayViewSet, LeaveRequestViewSet, PolicyView

# SimpleRouter: the other apps' routers already own the API root view.
router = SimpleRouter()
router.register(r"leave/requests", LeaveRequestViewSet, basename="leave")
router.register(r"leave/holidays", HolidayViewSet, basename="holiday")

urlpatterns = [
    path("leave/balance/", BalanceView.as_view(), name="leave-balance"),
    path("leave/balances/", BalancesView.as_view(), name="leave-balances"),
    path("leave/entitlements/", EntitlementView.as_view(), name="leave-entitlements"),
    path("leave/policy/", PolicyView.as_view(), name="leave-policy"),
    path("", include(router.urls)),
]
