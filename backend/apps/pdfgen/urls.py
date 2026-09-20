from django.urls import path

from .views import BulkPrintPreflightView, BulkPrintView, PdfBuildView, PdfDownloadView

urlpatterns = [
    path("documents/bulk-print/preflight/", BulkPrintPreflightView.as_view(), name="bulk-print-preflight"),
    path("documents/bulk-print/", BulkPrintView.as_view(), name="bulk-print"),
    path("documents/<int:document_id>/pdf/<str:kind>/", PdfBuildView.as_view(), name="pdf-build"),
    path("documents/<int:document_id>/pdf/<str:kind>/download/", PdfDownloadView.as_view(), name="pdf-download"),
]
