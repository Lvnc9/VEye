from django.contrib import admin

from .models import Document, DocumentSequence, SignOff


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
