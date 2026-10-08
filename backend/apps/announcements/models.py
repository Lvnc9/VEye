"""Company announcements (Phase 19, employee self-service).

The owner's decision (2026-10-08): HR (`manage_personnel`) and the مدیر عامل announce to the whole company;
any مسئول announces to their own node and everything beneath it. An announcement is plain text with an
optional pin and end date; it is never deleted — it is *withdrawn*, and then only the people who manage it
still see it. Its audience is fixed once published (changing who an announcement is for after people were
told would be a different announcement).
"""
from django.conf import settings
from django.db import models
from django.db.models import Index

from apps.core.models import TimeStampedModel
from apps.organization.models import OrgNode


class Announcement(TimeStampedModel):
    title = models.CharField(max_length=255)
    body = models.TextField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="announcements")
    #: Empty = the whole company. PROTECT: a node that was announced to cannot be deleted (archive it).
    audience_node = models.ForeignKey(
        OrgNode, null=True, blank=True, on_delete=models.PROTECT, related_name="announcements"
    )
    pinned = models.BooleanField(default=False)
    #: The last day it is shown in the current list; after that it moves to «بایگانی».
    expires_on = models.DateField(null=True, blank=True)
    #: Set when the title or text is changed after publishing, so readers can tell.
    edited_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    withdrawn_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-pinned", "-created_at", "-id"]
        indexes = [Index(fields=["withdrawn_at", "expires_on"], name="announce_live_idx")]

    def __str__(self):
        return self.title
