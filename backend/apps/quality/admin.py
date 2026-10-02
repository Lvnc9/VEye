from django.contrib import admin

from .models import InternalAudit, NonConformance, QualityEvent


@admin.register(NonConformance)
class NonConformanceAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "severity", "status", "owner_node", "reported_by", "created_at"]
    list_filter = ["status", "severity", "source"]
    search_fields = ["title", "description"]
    readonly_fields = [f.name for f in NonConformance._meta.fields]

    def has_add_permission(self, request):
        return False  # written only through quality.services, which records the history


@admin.register(QualityEvent)
class QualityEventAdmin(admin.ModelAdmin):
    list_display = ["id", "kind", "nc", "actor_name", "created_at"]
    list_filter = ["kind"]
    readonly_fields = [f.name for f in QualityEvent._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(InternalAudit)
class InternalAuditAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "status", "scope_node", "lead_auditor", "planned_on"]
    list_filter = ["status"]
    search_fields = ["title"]
    readonly_fields = [f.name for f in InternalAudit._meta.fields]

    def has_add_permission(self, request):
        return False  # written only through quality.services, which records the history
