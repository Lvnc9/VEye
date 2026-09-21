from django.contrib import admin

from .models import Company, Membership, OrgNode


class ReadOnlyAdmin(admin.ModelAdmin):
    """The tree is written only through apps/organization/tree.py (path, depth, parent_kind)
    and memberships only through memberships.py (exactly one primary per person). Editing a
    row here would bypass all of it."""

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


@admin.register(Membership)
class MembershipAdmin(ReadOnlyAdmin):
    list_display = ["user", "node", "is_primary", "is_lead", "position_label"]
    list_filter = ["is_primary", "is_lead"]
    search_fields = ["user__full_name", "node__name"]
