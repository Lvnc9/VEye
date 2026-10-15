from django.urls import path

from .views import AcknowledgeView, CoverageView, DocumentReadingView, PendingView

urlpatterns = [
    path("distribution/pending/", PendingView.as_view(), name="distribution-pending"),
    path("distribution/documents/<int:pk>/", DocumentReadingView.as_view(), name="distribution-document"),
    path("distribution/documents/<int:pk>/acknowledge/", AcknowledgeView.as_view(), name="distribution-acknowledge"),
    path("distribution/documents/<int:pk>/coverage/", CoverageView.as_view(), name="distribution-coverage"),
]
