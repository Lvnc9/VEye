from django.urls import path

from .views import PdfBuildView, PdfDownloadView

urlpatterns = [
    path("documents/<int:document_id>/pdf/<str:kind>/", PdfBuildView.as_view(), name="pdf-build"),
    path("documents/<int:document_id>/pdf/<str:kind>/download/", PdfDownloadView.as_view(), name="pdf-download"),
]
