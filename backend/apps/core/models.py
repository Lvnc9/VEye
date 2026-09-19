from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base model carrying created_at/updated_at, used across apps."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
