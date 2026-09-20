from django.apps import AppConfig


class PdfgenConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.pdfgen"
    label = "pdfgen"

    def ready(self):
        # Fonts are registered once per process, here, rather than by every
        # renderer instance as V_1.0 did (each PDFMaker re-registered them).
        # ReportLab's font registry is process-global, so this is the one piece
        # of shared state — written once at startup, read-only afterwards, which
        # is what makes concurrent builds safe.
        from .fonts import register_fonts

        register_fonts()
