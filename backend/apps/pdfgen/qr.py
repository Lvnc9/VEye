from io import BytesIO

import qrcode
from django.conf import settings


def verify_url(document) -> str:
    """Where a document's QR code points: the public verify page (Phase 5), keyed
    by the printed code and revision — e.g. `/verify/PR-01-01`. V_1.0 encoded a
    *predicted* static S3 URL of the PDF instead."""
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}/verify/{document.full_code}"


def qr_png(data: str) -> bytes:
    """PNG bytes of a QR code. Same parameters as V_1.0's utils.generate_qr
    (version 1 grown to fit, low error correction, 10px boxes, 4-box border) —
    but in memory: V_1.0 wrote these files into a shared ./qr directory."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    image = qr.make_image(fill="black", back_color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
