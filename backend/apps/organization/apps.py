from django.apps import AppConfig


class OrganizationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.organization"
    label = "organization"

    def ready(self):
        # New documents start from the company's defaults (Phase 11); see document_defaults.py.
        from apps.documents import services

        from .document_defaults import apply_to_new_document

        if apply_to_new_document not in services.NEW_DOCUMENT_HOOKS:
            services.NEW_DOCUMENT_HOOKS.append(apply_to_new_document)
