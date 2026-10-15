from django.conf import settings
from django.db import models


class ReadAcknowledgment(models.Model):
    """One person who must read one approved revision (Phase 21, owner's decision 2026-10-15). Written when
    the revision is approved (`services.distribute`) for everyone placed in its owner node's subtree and in
    the subtrees of the units named in its مسئولیت ها block — fixed then, so moving people later does not
    rewrite who was asked. `acknowledged_at` is when they pressed «مطالعه کردم». A new revision is a new
    document row, so it asks again; the old revision's rows stay as its record."""

    document = models.ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="read_acknowledgments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="read_acknowledgments")
    # Where they were placed when it was distributed — the coverage report groups by it.
    node_name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["node_name", "user__full_name", "id"]
        constraints = [models.UniqueConstraint(fields=["document", "user"], name="uniq_read_ack_document_user")]
        indexes = [models.Index(fields=["user", "acknowledged_at"], name="read_ack_user_pending")]

    def __str__(self):
        return f"{self.user_id} → {self.document_id} {'read' if self.acknowledged_at else 'pending'}"
