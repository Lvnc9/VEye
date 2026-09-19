from django.urls import path

from .views import DashboardMetricsView, DashboardSystemInfoView

urlpatterns = [
    path("dashboard/metrics/", DashboardMetricsView.as_view(), name="dashboard-metrics"),
    path("dashboard/system-info/", DashboardSystemInfoView.as_view(), name="dashboard-system-info"),
]
