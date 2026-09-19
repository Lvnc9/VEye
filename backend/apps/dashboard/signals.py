from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.accounts.models import User
from apps.documents.models import Document

from .views import METRICS_CACHE_KEY, SYSTEM_INFO_CACHE_KEY


@receiver([post_save, post_delete], sender=Document)
def invalidate_metrics_cache(sender, **kwargs):
    cache.delete(METRICS_CACHE_KEY)


@receiver([post_save, post_delete], sender=User)
def invalidate_system_info_cache(sender, **kwargs):
    cache.delete(SYSTEM_INFO_CACHE_KEY)
