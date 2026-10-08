from django.contrib import admin

from .models import LeaveRequest


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ["id", "requester", "leave_type", "starts_on", "ends_on", "status", "decided_by_name"]
    list_filter = ["status", "leave_type"]
    readonly_fields = [f.name for f in LeaveRequest._meta.fields]

    def has_add_permission(self, request):
        return False  # written only through leave.services
