from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import SECRET_KEY, SETUP_TOKEN, env

DEBUG = False

# Fail fast rather than silently serving production traffic signed with the
# dev fallback key — it also signs every JWT.
if SECRET_KEY.startswith("insecure-dev-key"):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in production.")

# The setup token is a password that lets anyone who knows it create the most powerful account
# on a fresh database; when one is set it must not be guessable. (Unset is fine: it disables setup.)
if SETUP_TOKEN and len(SETUP_TOKEN.encode("utf-8")) < 32:
    raise ImproperlyConfigured("VEYE_SETUP_TOKEN must be at least 32 bytes when set.")

JWT_COOKIE_SECURE = True

# ---------------------------------------------------------------------------
# Security hardening
# ---------------------------------------------------------------------------
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 30)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
