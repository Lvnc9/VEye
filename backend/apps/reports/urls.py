from django.urls import path

from .views import DocumentsExportView, ProjectsExportView

urlpatterns = [
    path("reports/documents/export/", DocumentsExportView.as_view(), name="reports-documents-export"),
    path("reports/projects/export/", ProjectsExportView.as_view(), name="reports-projects-export"),
]
