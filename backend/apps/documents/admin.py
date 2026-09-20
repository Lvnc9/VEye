from django.contrib import admin

from .models import Document, DocumentEvent, DocumentSequence, SignOff


class SignOffInline(admin.TabularInline):
    model = SignOff
    extra = 0


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["full_code", "title", "group", "category", "status", "created_by", "created_at"]
    list_filter = ["group", "category", "status"]
    search_fields = ["title"]
    raw_id_fields = ["previous_revision", "created_by"]
    inlines = [SignOffInline]
    # number/revision are allocated by the service layer; editing them by hand
    # would bypass the sequence lock and the code-uniqueness guarantees.
    readonly_fields = ["number", "revision", "previous_revision", "created_by"]


@admin.register(DocumentSequence)
class DocumentSequenceAdmin(admin.ModelAdmin):
    list_display = ["group", "last_number"]


@admin.register(DocumentEvent)
class DocumentEventAdmin(admin.ModelAdmin):
    list_display = ["document", "kind", "from_status", "to_status", "actor_name", "created_at"]
    list_filter = ["kind"]
    search_fields = ["document__title", "actor_name"]
    # An audit trail is only worth anything if nobody edits it.
    readonly_fields = [f.name for f in DocumentEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
