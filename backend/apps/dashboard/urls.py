from django.urls import path

from .views import DashboardAwaitingView, DashboardMetricsView, DashboardSystemInfoView

urlpatterns = [
    path("dashboard/metrics/", DashboardMetricsView.as_view(), name="dashboard-metrics"),
    path("dashboard/awaiting/", DashboardAwaitingView.as_view(), name="dashboard-awaiting"),
    path("dashboard/system-info/", DashboardSystemInfoView.as_view(), name="dashboard-system-info"),
]
