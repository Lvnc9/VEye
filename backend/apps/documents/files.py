"""Validation and normalization for uploaded files and logos."""
import hashlib
import io
import os

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.exceptions import ValidationError

from apps.core.constants import FILE_EXTENSIONS, FileKind

#: Logos are drawn at 50-70pt in the PDF; anything larger than this is wasted
#: bytes, and it bounds the memory Pillow needs.
LOGO_MAX_EDGE = 1024
LOGO_MAX_PIXELS = 25_000_000
_LOGO_FORMATS = {"PNG", "JPEG", "WEBP"}


def extension_of(name: str) -> str:
    return os.path.splitext(name)[1].lstrip(".").lower()


def kind_for(name: str) -> str | None:
    """The FileKind an upload belongs to, decided by extension on the server.
    The client's own idea of what it is uploading is never trusted."""
    extension = extension_of(name)
    for kind, extensions in FILE_EXTENSIONS.items():
        if extension in extensions:
            return kind
    return None


def _megabytes(size: int) -> str:
    return f"{size / (1024 * 1024):.0f}"


def inspect_upload(upload) -> tuple[str, str, int]:
    """Validate an uploaded document file. Returns (kind, sha256, size).

    The file is hashed in chunks (videos can be large) and then rewound so the
    caller can store it.
    """
    name = os.path.basename(upload.name or "")
    if not name:
        raise ValidationError({"file": ["فایلی ارسال نشده است."]})

    kind = kind_for(name)
    if kind is None:
        allowed = "، ".join(sorted({e for exts in FILE_EXTENSIONS.values() for e in exts}))
        raise ValidationError({"file": [f"این نوع فایل مجاز نیست. فرمت‌های مجاز: {allowed}"]})

    limit = settings.DOCUMENT_FILE_MAX_BYTES
    if upload.size > limit:
        raise ValidationError({"file": [f"حجم فایل نباید بیش از {_megabytes(limit)} مگابایت باشد."]})
    if upload.size == 0:
        raise ValidationError({"file": ["فایل خالی است."]})

    digest = hashlib.sha256()
    for chunk in upload.chunks():
        digest.update(chunk)
    upload.seek(0)
    return kind, digest.hexdigest(), upload.size


def normalize_logo(upload) -> ContentFile:
    """Validate a logo and re-encode it as a PNG.

    Re-encoding (rather than trusting the upload) does three things: it proves the
    bytes really are an image, it strips EXIF/metadata, and it gives the PDF
    renderer the one format it can draw — it paints a black box for a non-PNG
    logo (to_make_pdf.py:159-160).
    """
    limit = settings.LOGO_MAX_BYTES
    if upload.size > limit:
        raise ValidationError({"logo": [f"حجم لوگو نباید بیش از {_megabytes(limit)} مگابایت باشد."]})

    bad_image = ValidationError({"logo": ["فایل انتخاب‌شده تصویر معتبری نیست. از PNG یا JPEG استفاده کنید."]})
    try:
        probe = Image.open(upload)
        probe.verify()  # verify() invalidates the image object, so reopen below
        upload.seek(0)
        image = Image.open(upload)
        if image.format not in _LOGO_FORMATS:
            raise bad_image
        if image.width * image.height > LOGO_MAX_PIXELS:
            raise ValidationError({"logo": ["ابعاد تصویر بیش از حد بزرگ است."]})
        image = ImageOps.exif_transpose(image)  # phone photos carry their rotation in EXIF
        image.load()
    except ValidationError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError):
        raise bad_image

    image.thumbnail((LOGO_MAX_EDGE, LOGO_MAX_EDGE))
    if image.mode not in ("RGB", "RGBA", "L", "LA"):
        image = image.convert("RGBA")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return ContentFile(buffer.getvalue())


#: A drawn signature is a few kilobytes; the pad exports at most ~1000 px wide.
SIGNATURE_MAX_BYTES = 2 * 1024 * 1024
SIGNATURE_MAX_EDGE = 1000
SIGNATURE_MAX_PIXELS = 4_000_000
#: A pad that was only touched, or never touched, produces (almost) no ink.
SIGNATURE_MIN_INK_PIXELS = 30
_SIGNATURE_FORMATS = {"PNG", "JPEG", "WEBP"}


def normalize_signature(upload) -> ContentFile:
    """Validate a signature from the web pad and re-encode it as an opaque RGB PNG.

    Opaque, because the PDF renderer draws signatures without a mask (V_1.0's
    archived ones were opaque): a transparent PNG would print as a black box.
    Re-encoding also proves the bytes are an image and strips metadata. A blank
    pad is refused — an empty rectangle is not a signature.
    """
    bad_image = ValidationError({"signature": ["امضا معتبر نیست. دوباره امضا کنید."]})
    if upload is None:
        raise ValidationError({"signature": ["امضا ارسال نشده است."]})
    if upload.size > SIGNATURE_MAX_BYTES:
        raise ValidationError({"signature": ["حجم امضا بیش از حد مجاز است."]})

    try:
        probe = Image.open(upload)
        probe.verify()
        upload.seek(0)
        image = Image.open(upload)
        if image.format not in _SIGNATURE_FORMATS:
            raise bad_image
        if image.width * image.height > SIGNATURE_MAX_PIXELS:
            raise ValidationError({"signature": ["ابعاد امضا بیش از حد بزرگ است."]})
        image.load()
    except ValidationError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError):
        raise bad_image

    rgba = image.convert("RGBA")
    flat = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    flat.alpha_composite(rgba)
    flat = flat.convert("RGB")
    flat.thumbnail((SIGNATURE_MAX_EDGE, SIGNATURE_MAX_EDGE))

    # Count "ink": pixels clearly darker than the paper.
    ink = sum(1 for value in flat.convert("L").getdata() if value < 200)
    if ink < SIGNATURE_MIN_INK_PIXELS:
        raise ValidationError({"signature": ["امضا خالی است. لطفاً امضا کنید."]})

    buffer = io.BytesIO()
    flat.save(buffer, format="PNG", optimize=True)
    return ContentFile(buffer.getvalue())
