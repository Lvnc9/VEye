from django.contrib import admin

from .models import ImportRun


@admin.register(ImportRun)
class ImportRunAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "dry_run", "total", "processed", "started_at", "finished_at")
    list_filter = ("status", "dry_run")
    # A run is the record of what an import did; editing it would falsify that.
    readonly_fields = [f.name for f in ImportRun._meta.fields]

    def has_add_permission(self, request):
        return False
