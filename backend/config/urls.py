from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.organization.urls")),
    path("api/v1/", include("apps.projects.urls")),
    # pdfgen first: its documents/bulk-print/ must win over the documents router's documents/<pk>/.
    path("api/v1/", include("apps.pdfgen.urls")),
    path("api/v1/", include("apps.documents.urls")),
    path("api/v1/", include("apps.dashboard.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
