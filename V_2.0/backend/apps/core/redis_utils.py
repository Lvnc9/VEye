"""Small helpers around the django-redis cache backend for the two raw-Redis
use cases in this project that don't fit Django's cache.get/set API well:
the JWT blacklist (needs TTL'd key existence checks) and the per-prefix
atomic document code counters (needs INCR).

Both call sites fall back gracefully if Redis is unreachable, per
skeleton.md §6/§9 — see apps/documents/services.py and
apps/accounts/authentication.py for the fallback behavior itself.
"""
from __future__ import annotations

import logging

from django.core.cache import cache

logger = logging.getLogger("veye")


def get_raw_redis_client():
    """Returns the underlying redis-py client behind django-redis's default
    cache, or None if unavailable (e.g. the 'default' cache isn't a
    django-redis backend, or Redis is down)."""
    try:
        return cache.client.get_client(write=True)
    except Exception:  # pragma: no cover - defensive, e.g. Redis down
        logger.warning("Redis client unavailable", exc_info=True)
        return None
