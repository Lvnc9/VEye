from django.contrib import admin

from .models import Company, OrgNode


class ReadOnlyAdmin(admin.ModelAdmin):
    """The tree is written only through apps/organization/tree.py, which keeps path, depth
    and parent_kind consistent. Editing a row here would bypass all of it."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OrgNode)
class OrgNodeAdmin(ReadOnlyAdmin):
    list_display = ["name", "kind", "depth", "is_active", "path"]
    list_filter = ["kind", "is_active"]
    search_fields = ["name"]


@admin.register(Company)
class CompanyAdmin(ReadOnlyAdmin):
    list_display = ["root", "legal_name", "setup_step", "setup_completed_at"]
