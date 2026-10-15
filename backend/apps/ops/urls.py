from django.urls import path

from .views import BackupListView, BackupRunView

urlpatterns = [
    path("ops/backups/", BackupListView.as_view(), name="ops-backups"),
    path("ops/backups/run/", BackupRunView.as_view(), name="ops-backups-run"),
]
