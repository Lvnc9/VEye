from django.contrib import admin

from .models import Announcement


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "author", "audience_node", "pinned", "expires_on", "withdrawn_at"]
    readonly_fields = [f.name for f in Announcement._meta.fields]

    def has_add_permission(self, request):
        return False  # written only through announcements.services
