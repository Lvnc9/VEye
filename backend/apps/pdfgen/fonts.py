from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def register_fonts() -> None:
    """Register the vendored Vazir pair under the names the renderer uses.

    The renderer builds the bold name by string concatenation
    (`font_name + "-Bold"`) in nine places, so the two names must be exactly
    `PDF_FONT_NAME` and `PDF_FONT_NAME + "-Bold"`.
    """
    name = settings.PDF_FONT_NAME
    faces = ((name, settings.PDF_FONT_REGULAR), (f"{name}-Bold", settings.PDF_FONT_BOLD))
    registered = set(pdfmetrics.getRegisteredFontNames())
    for face, path in faces:
        if face in registered:
            continue
        if not path.is_file():
            raise ImproperlyConfigured(f"PDF font file not found: {path}")
        pdfmetrics.registerFont(TTFont(face, str(path)))
