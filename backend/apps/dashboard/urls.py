from django.urls import path

from .views import DashboardAwaitingView, DashboardInboxView, DashboardMetricsView, DashboardSystemInfoView

urlpatterns = [
    path("dashboard/metrics/", DashboardMetricsView.as_view(), name="dashboard-metrics"),
    path("dashboard/awaiting/", DashboardAwaitingView.as_view(), name="dashboard-awaiting"),
    path("dashboard/inbox/", DashboardInboxView.as_view(), name="dashboard-inbox"),
    path("dashboard/system-info/", DashboardSystemInfoView.as_view(), name="dashboard-system-info"),
]
