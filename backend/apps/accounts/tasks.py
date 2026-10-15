from celery import shared_task
from django.conf import settings
from django.utils import timezone


@shared_task(name="accounts.purge_login_events")
def purge_login_events() -> int:
    """Sign-in history is kept `LOGIN_HISTORY_DAYS` (default 90; Phase 20) — long enough to notice a
    stranger's attempts, short enough not to become a record of everyone's comings and goings."""
    from .models import LoginEvent

    cutoff = timezone.now() - timezone.timedelta(days=settings.LOGIN_HISTORY_DAYS)
    deleted, _ = LoginEvent.objects.filter(created_at__lt=cutoff).delete()
    return deleted
