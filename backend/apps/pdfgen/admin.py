from django.contrib import admin

from .models import PdfBuild


@admin.register(PdfBuild)
class PdfBuildAdmin(admin.ModelAdmin):
    list_display = ("document", "kind", "status", "built_at", "size", "requested_by")
    list_filter = ("kind", "status")
    search_fields = ("document__title",)
    # A build row is the worker's record of a file on disk; editing it by hand
    # would make it lie about that file.
    readonly_fields = [field.name for field in PdfBuild._meta.fields]

    def has_add_permission(self, request):
        return False
