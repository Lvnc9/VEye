from django.apps import AppConfig


class DashboardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.dashboard"
    label = "dashboard"

    def ready(self):
        # Wires the cache-invalidation signals onto apps.documents /
        # apps.accounts models — dashboard has no models of its own
        # (skeleton.md §3), so it reaches into those apps' signals instead
        # of the other way around.
        from . import signals  # noqa: F401
