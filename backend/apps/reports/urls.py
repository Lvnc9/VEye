from django.urls import path

from .views import DocumentsExportView, KpiView, NonConformancesExportView, ProjectsExportView

urlpatterns = [
    path("reports/documents/export/", DocumentsExportView.as_view(), name="reports-documents-export"),
    path("reports/projects/export/", ProjectsExportView.as_view(), name="reports-projects-export"),
    path("reports/quality/export/", NonConformancesExportView.as_view(), name="reports-quality-export"),
    path("reports/kpi/", KpiView.as_view(), name="reports-kpi"),
]
